import os
import logging
import uuid
import asyncio
from dotenv import load_dotenv
from gemini_tool_definitions import SEARCH_PRODUCTS_TOOL
from utils import normalize_product

# Load environment variables
load_dotenv()

class GeminiLive2Service:
    """
    Modular service for Gemini Live2 (audio, video, VAD, camera, etc.).
    - Audio streaming: production-ready
    - Video/image streaming: stubbed for future extension
    - Diagnostics and test hooks included
    - All configuration from .env
    - No hardcoded secrets
    - All changes are modular and do not affect other chat modes
    """
    def __init__(self, loop=None):
        """Initialize the Gemini Live2 Service for VAD+Camera+Audio (modular, robust). Accepts an optional asyncio event loop."""
        self.model_name = os.getenv("GEMINI_LIVE2_MODEL", "gemini-2.0-flash-live-001")
        self.sessions = {}  # session_id -> session state
        self.system_instruction = os.getenv("GEMINI_LIVE_INSTRUCTIONS", "You are an intelligent assistant that helps users find products, answer questions, and provide helpful information. You can search for products when asked. When responding with audio, keep your responses concise and natural.")
        self.tools = [SEARCH_PRODUCTS_TOOL]
        self.loop = loop
        logging.info(f"[Live2] Using Gemini model: {self.model_name}")
        # Add any additional config as needed

    def create_session(self):
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "audio": [],
            "active": True,
            "out_queue": asyncio.Queue(maxsize=10),
            "socketio": None,
            "client_sid": None,
            "stream_task": None,
        }
        logging.info(f"[Live2] Created session {session_id}")
        return session_id

    def set_socketio(self, session_id, socketio, client_sid):
        if session_id in self.sessions:
            self.sessions[session_id]["socketio"] = socketio
            self.sessions[session_id]["client_sid"] = client_sid

    async def process_streaming(self, session_id):
        """
        Async task: reads audio and video from out_queue, streams to Gemini, emits responses.
        Modular: audio and video streaming are independent.
        """
        import google.genai as genai
        from google.genai import types
        logger = logging.getLogger(__name__)
        logger.info(f"[Live2] process_streaming started for session {session_id}")
        try:
            session = self.sessions[session_id]
            model = self.model_name
            api_key = os.getenv("GEMINI_API_KEY")
            client = genai.Client(api_key=api_key)
            config = types.LiveConnectConfig(
                system_instruction=types.Content(parts=[types.Part(text=self.system_instruction)]),
                response_modalities=["AUDIO", "TEXT"],
                tools=self.tools,
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                    ),
                    language_code='en-US',
                ),
                output_audio_transcription=types.AudioTranscriptionConfig(),
            )
            logger.info(f"[Live2] Using Gemini model: {model} with config: {config}")
            async with client.aio.live.connect(model=model, config=config) as gemini_session:
                session["gemini_session"] = gemini_session
                socketio = session["socketio"]
                client_sid = session["client_sid"]
                # Notify frontend Gemini session is ready for video frames
                if socketio and client_sid:
                    socketio.emit('live2_session_ready', {'session_id': session_id}, room=client_sid, namespace="/live2")
                # Start sender in parallel
                sender_task = asyncio.create_task(self._send_to_gemini(session_id, gemini_session))
                while session["active"]:
                    try:
                        # --- RECEIVE RESPONSES ---
                        logger.info(f"[Live2] Entering Gemini receive loop for session {session_id}")
                        async for response in gemini_session.receive():
                            try:
                                # Handle function/tool call
                                if hasattr(response, 'tool_call') and response.tool_call:
                                    function_call_details = response.tool_call.function_calls[0]
                                    function_name = function_call_details.name
                                    function_args = dict(function_call_details.args)
                                    logger.info(f"[Live2] Function call: {function_name} with args {function_args}")
                                    if function_name == "search_products":
                                        query = function_args.get("query", "")
                                        product = normalize_product({"id": "1", "name": f"Result for {query}"}, query=query)
                                        results = [product]
                                        if socketio and client_sid:
                                            socketio.emit('live2_message', {"text": f"Function result: {results}", "sender": "Gemini", "function_name": function_name, "results": results}, room=client_sid, namespace="/live2")
                                # Handle text response
                                if hasattr(response, 'text') and response.text:
                                    logger.info(f"[Live2] Emitting text response to client: {response.text}")
                                    if socketio and client_sid:
                                        socketio.emit('live2_message', {"text": response.text, "sender": "Gemini"}, room=client_sid, namespace="/live2")
                                # Handle audio response
                                if hasattr(response, 'audio') and response.audio:
                                    logger.info(f"[Live2] Emitting audio response to client, size={len(response.audio)} bytes")
                                    import base64
                                    audio_b64 = base64.b64encode(response.audio).decode('utf-8')
                                    if socketio and client_sid:
                                        socketio.emit('live2_audio', {"audio": audio_b64}, room=client_sid, namespace="/live2")
                                # (Optional) Handle transcription
                                if hasattr(response, 'output_transcription') and response.output_transcription:
                                    logger.info(f"[Live2] Emitting output transcription: {response.output_transcription.text}")
                                    if socketio and client_sid:
                                        socketio.emit('live2_message', {"text": response.output_transcription.text, "sender": "Gemini", "transcription": True}, room=client_sid, namespace="/live2")
                                if hasattr(response, 'input_transcription') and response.input_transcription:
                                    logger.info(f"[Live2] Emitting input transcription: {response.input_transcription.text}")
                                    if socketio and client_sid:
                                        socketio.emit('live2_message', {"text": response.input_transcription.text, "sender": "User", "transcription": True}, room=client_sid, namespace="/live2")
                            except Exception as emit_err:
                                logger.error(f"[Live2] Error emitting Gemini response: {emit_err}")
                    except Exception as e:
                        logger.error(f"[Live2] Error in streaming loop: {e}")
                # Cancel sender when session ends
                sender_task.cancel()
                try:
                    await sender_task
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"[Live2] Exception in process_streaming for session {session_id}: {e}", exc_info=True)

    def handle_audio_chunk(self, session_id, pcm_bytes):
        """
        Handle incoming audio chunk (PCM bytes) for a session.
        Modular: does not affect video or other chat modes.
        """
        if session_id not in self.sessions or not self.sessions[session_id]["active"]:
            logging.warning(f"[Live2] Invalid or inactive session: {session_id}")
            return {"error": "Invalid session"}
        session = self.sessions[session_id]
        if "out_queue" in session:
            logging.info(f"[Live2] Putting audio chunk in out_queue for session {session_id}, size={len(pcm_bytes)} bytes, type={type(pcm_bytes)}")
            try:
                if self.loop:
                    asyncio.run_coroutine_threadsafe(session["out_queue"].put({"data": pcm_bytes, "mime_type": "audio/pcm"}), self.loop)
                else:
                    logging.error("[Live2] No event loop set for GeminiLive2Service!")
            except Exception as e:
                logging.error(f"[Live2] Error putting audio in out_queue: {e}")
        session["audio"].append(pcm_bytes)
        logging.info(f"[Live2] Received audio chunk for session {session_id}, size={len(pcm_bytes)} bytes")
        return {"status": "audio chunk received"}

    def handle_video_frame(self, session_id, frame_data_url):
        if session_id not in self.sessions or not self.sessions[session_id]["active"]:
            logging.warning(f"[Live2] Invalid or inactive session for video: {session_id}")
            return {"error": "Invalid session"}
        session = self.sessions[session_id]
        # Direct-send: send frame to Gemini session immediately if available
        if "gemini_session" in session and session["gemini_session"]:
            try:
                if self.loop:
                    header, encoded = frame_data_url.split(",", 1)
                    frame_bytes = base64.b64decode(encoded)
                    asyncio.run_coroutine_threadsafe(
                        session["gemini_session"].send(
                            input={"data": frame_bytes, "mime_type": "image/jpeg"},
                            end_of_turn=False
                        ),
                        self.loop
                    )
                    logging.info(f"[Live2] Direct-sent video frame to Gemini for session {session_id}, size={len(frame_bytes)} bytes")
                else:
                    logging.error("[Live2] No event loop set for GeminiLive2Service!")
            except Exception as e:
                logging.error(f"[Live2] Error direct-sending video frame to Gemini: {e}")
        else:
            logging.warning(f"[Live2] No active Gemini session for video frame in session {session_id}")
        return {"status": "video frame sent"}

    async def _send_to_gemini(self, session_id, gemini_session):
        session = self.sessions[session_id]
        while session["active"]:
            try:
                item = await session["out_queue"].get()
                try:
                    await gemini_session.send(input=item, end_of_turn=False)
                    logging.info(f"[Live2] Sent {item['mime_type']} to Gemini for session {session_id}, size={len(item['data'])} bytes")
                except Exception as e:
                    logging.error(f"[Live2] Error sending to Gemini: {e}")
            except Exception as e:
                logging.error(f"[Live2] Error in send_to_gemini loop: {e}")
                await asyncio.sleep(1)

    def end_session(self, session_id):
        """
        End a session. Modular: does not affect other sessions or chat modes.
        """
        if session_id in self.sessions:
            self.sessions[session_id]["active"] = False
            logging.info(f"[Live2] Ended session {session_id}")
            return True
        return False

    # --- DIAGNOSTICS ---
    def get_status(self):
        """
        Return a summary of all active sessions for diagnostics.
        Modular: does not affect any chat mode logic.
        """
        return {
            "active_sessions": [sid for sid, s in self.sessions.items() if s["active"]],
            "total_sessions": len(self.sessions)
        }

    # --- TEST HOOKS ---
    def _reset(self):
        """
        Reset all sessions (for unit tests only).
        Modular: does not affect production logic.
        """
        self.sessions = {}

    # (Optional) Future: Implement session management, video/image streaming, VAD, etc. as modular hooks.

    # TODO: Implement session management, audio/camera streaming, VAD, etc.
    # Methods should be modular and not affect existing Live mode 