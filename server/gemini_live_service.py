import os
import json
import asyncio
import logging
import base64
import uuid
from google import genai
from google.genai import types
from google.genai.types import Tool, Part, Content, FunctionResponse
from google.cloud import texttospeech
import aiohttp
from dotenv import load_dotenv
from gemini_tool_definitions import SEARCH_PRODUCTS_TOOL
import websockets
from dotenv import load_dotenv
from gemini_tool_definitions import SEARCH_PRODUCTS_TOOL
from utils import normalize_product

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get API keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY not found in environment variables")
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Configure Gemini API
# Use Client instead of configure for the newer API style
genai_client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1beta'})

class GeminiLiveService:
    def __init__(self, loop=None):
        """Initialize the Gemini Live Service with API clients and session management"""
        logger.info("Initializing GeminiLiveService")
        
        # Store the asyncio event loop
        if loop is None:
            # Get the current event loop if none is provided, or create a new one
            # This might be useful if the service is run independently
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError: # No running event loop
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
        else:
            self.loop = loop
        
        # Get the model name from environment variables
        self.model_name = os.getenv("GEMINI_LIVE_MODEL", "gemini-2.0-flash-live-001")
        logger.info(f"Using Gemini Live model: {self.model_name}")
        
        # Initialize Text-to-Speech client
        try:
            self.tts_client = texttospeech.TextToSpeechClient()
            
            # Get TTS configuration from environment variables
            tts_language = os.getenv("TTS_LANGUAGE_CODE", "en-US")
            tts_voice = os.getenv("TTS_VOICE_NAME", "en-US-Neural2-F")
            
            self.voice = texttospeech.VoiceSelectionParams(
                language_code=tts_language,
                name=tts_voice
            )
            
            # Storage for responses and session state
            self.session_responses = {}
            
            # Get audio encoding from environment variables or use default
            audio_encoding_str = os.getenv("TTS_AUDIO_ENCODING", "MP3")
            audio_encoding = getattr(texttospeech.AudioEncoding, audio_encoding_str, texttospeech.AudioEncoding.MP3)
            
            self.audio_config = texttospeech.AudioConfig(
                audio_encoding=audio_encoding
            )
            logger.info("Text-to-Speech client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Text-to-Speech client: {e}")
            self.tts_client = None
        
        # Session management
        self.active_sessions = {}
        
        # Configure generation parameters from environment variables
        self.temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
        self.top_p = float(os.getenv("GEMINI_TOP_P", "0.95"))
        self.top_k = int(os.getenv("GEMINI_TOP_K", "40"))
        self.max_output_tokens = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "2048"))
        
        # Configure tools for the Live API
        self.tools = [Tool(function_declarations=[SEARCH_PRODUCTS_TOOL])]
        
        # Get system instructions from environment variables
        default_instructions = """You are an intelligent assistant that helps users find products, 
            answer questions, and provide helpful information. You can search for products when asked.
            When responding with audio, keep your responses concise and natural."""
            
        self.system_instruction = os.getenv("GEMINI_LIVE_INSTRUCTIONS", default_instructions)
        
        logger.info("GeminiLiveService initialized successfully")
    
    async def _session_background_task(self, session_id):
        """Background task that maintains a persistent connection for a session"""
        session_data = self.active_sessions[session_id]
        config = session_data["config"]
        message_queue = session_data["message_queue"]
        response_queue = session_data["response_queue"]
        logger.info(f"Starting background task for session {session_id}")
        try:
            # Create a live config for the session
            logger.info(f"[DEBUG] System instruction before session: {self.system_instruction}")
            logger.info(f"[DEBUG] Tools before session: {self.tools}")
            live_config = types.LiveConnectConfig(
                system_instruction=Content(
                    parts=[Part(text=self.system_instruction)]
                ),
                response_modalities=["TEXT"],
                tools=self.tools
            )
        except Exception as e:
            logger.error(f"Error creating live config for session {session_id}: {e}")
            session_data["connected"] = False
            return
        try:
            logger.info(f"[DEBUG] Attempting to create Gemini client for session {session_id} with model: {self.model_name}")
            logger.info(f"[DEBUG] Using API key: {GEMINI_API_KEY[:6]}... (truncated)")
            client = genai.Client(api_key=GEMINI_API_KEY)
            logger.info(f"[DEBUG] Gemini client created successfully for session {session_id}")
            logger.info(f"[DEBUG] Attempting aio.live.connect for session {session_id} with model: {self.model_name}")
            async with client.aio.live.connect(model=self.model_name, config=live_config) as session:
                logger.info(f"Session {session_id} initialized successfully")
                session_data["connected"] = True
                session_data["gemini_session"] = session
                while True:
                    try:
                        message = await message_queue.get()
                        if message is None:
                            logger.info(f"Terminating session {session_id} by request")
                            break
                        logger.info(f"Processing message for session {session_id}: {str(message)[:50]}...")
                        self.session_responses[session_id] = {"text": "", "done": False, "audio": None}
                        # Multimodal: combine text and latest frame if present
                        if isinstance(message, tuple):
                            message, frame = message
                        else:
                            message, frame = message, None
                        if message is None:
                            logger.info(f"Terminating session {session_id} by request")
                            break
                        logger.info(f"Processing message for session {session_id}: {str(message)[:50]}... (frame={'yes' if frame else 'no'})")
                        # Multimodal: combine text and latest frame if present
                        if frame:
                            try:
                                header, encoded = frame.split(",", 1)
                                mime_type = header.split(":")[1].split(";")[0] if ":" in header and ";" in header else "image/jpeg"
                                frame_bytes = base64.b64decode(encoded)
                                parts = [message, Part.from_bytes(data=frame_bytes, mime_type=mime_type)]
                                logger.info(f"[LiveChat] Sending multimodal input to Gemini: text+image ({mime_type}, {len(frame_bytes)} bytes)")
                                await session.send(input=parts, end_of_turn=True)
                            except Exception as e:
                                logger.error(f"[LiveChat] Error processing video frame for multimodal input: {e}")
                                # Emit error to frontend and skip Gemini call
                                socketio = session_data.get("socketio")
                                client_sid = session_data.get("client_sid")
                                if socketio and client_sid:
                                    socketio.emit('response_complete', {"text": "[Error: Could not process image frame]"}, room=client_sid)
                                continue
                        else:
                            logger.info(f"[LiveChat] Sending text-only input to Gemini")
                            await session.send(input=message, end_of_turn=True)
                        accumulated_text = ""
                        # --- Inner response loop: handle Gemini responses for this message ---
                        async for response in session.receive():
                            # 1. Handle text responses (emit response_chunk)
                            if hasattr(response, "text") and response.text:
                                accumulated_text += response.text
                                if "socketio" in session_data and "client_sid" in session_data:
                                    socketio = session_data["socketio"]
                                    client_sid = session_data["client_sid"]
                                    socketio.emit('response_chunk', {
                                        'session_id': session_id,
                                        'text': response.text,
                                        'done': False
                                    }, room=client_sid)
                            # 2. Handle tool calls (function calls)
                            if hasattr(response, "tool_call") and response.tool_call:
                                function_call_details = response.tool_call.function_calls[0]
                                tool_call_id = function_call_details.id
                                function_name = function_call_details.name
                                function_args = dict(function_call_details.args)
                                logger.info(f"Function call in session {session_id}: {function_name} with args {function_args}")
                                function_response = await self._execute_function(function_name, function_args)
                                if function_name == "search_products" and function_response and "results" in function_response:
                                    if "socketio" in session_data and "client_sid" in session_data:
                                        socketio = session_data["socketio"]
                                        client_sid = session_data["client_sid"]
                                        enriched_results = [normalize_product(product) for product in function_response["results"]]
                                        socketio.emit('function_result', {
                                            'session_id': session_id,
                                            'function_name': function_name,
                                            'results': enriched_results
                                        }, room=client_sid)
                                    session_data["_function_result_sent"] = True
                                    # Immediately emit response_complete if not already sent for this message
                                    if not session_data.get('_response_complete_sent'):
                                        socketio.emit('response_complete', {
                                            'session_id': session_id,
                                            'text': "Here you go!",  # Or use accumulated_text if you prefer
                                            'done': True
                                        }, room=client_sid)
                                        session_data['_response_complete_sent'] = True
                                func_resp = types.FunctionResponse(
                                    id=tool_call_id,
                                    name=function_name,
                                    response={"content": function_response}
                                )
                                await session.send(input=func_resp, end_of_turn=False)
                                break  # --- Only break the inner response loop ---
                            # 3. End of turn: emit response_complete and break
                            if hasattr(response, "end_of_turn") and response.end_of_turn:
                                final_text = accumulated_text.strip()
                                if not final_text and session_data.get("_function_result_sent"):
                                    final_text = "Here you go!"
                                    session_data['_function_result_sent'] = False
                                if "socketio" in session_data and "client_sid" in session_data:
                                    socketio = session_data["socketio"]
                                    client_sid = session_data["client_sid"]
                                    socketio.emit('response_complete', {
                                        'session_id': session_id,
                                        'text': final_text,
                                        'done': True
                                    }, room=client_sid)
                                break  # --- Only break the inner response loop ---
                        # Always emit response_complete at the end
                        socketio = session_data.get("socketio")
                        client_sid = session_data.get("client_sid")
                        if socketio and client_sid and not session_data.get('_response_complete_sent'):
                            socketio.emit('response_complete', {"session_id": session_id, "text": accumulated_text, "done": True}, room=client_sid)
                            session_data['_response_complete_sent'] = True
                            await self.stream_tts_audio(session_id, accumulated_text, socketio, client_sid)
                        elif not socketio or not client_sid:
                            logger.error(f"[LiveChat] Cannot emit response_complete: socketio or client_sid missing for session {session_id}")
                        # Reset the safeguard for the next message
                        session_data['_response_complete_sent'] = False
                        # Mark the response as done
                        self.session_responses[session_id]["done"] = True
                        await response_queue.put(True)
                        logger.info(f"[LiveChat] Gemini response: {response}")
                        if hasattr(response, 'tool_call') and response.tool_call:
                            logger.info(f"[LiveChat] Tool call detected: {response.tool_call}")
                        else:
                            logger.info(f"[LiveChat] No tool_call in response. Response keys: {dir(response)}")
                    except asyncio.TimeoutError:
                        pass
            session_data["connected"] = False
            session_data["task"] = None
            logger.info(f"Background task for session {session_id} has ended")
        except Exception as e:
            logger.error(f"[CRITICAL] Failed to connect Gemini Live session for {session_id}: {type(e).__name__} - {e}")
            session_data["connected"] = False
            return
    
    async def create_session(self, session_id=None, config=None):
        """Create a new session for the Gemini Live API"""
        # Generate a session ID if not provided
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        # Initialize configuration if not provided
        if config is None:
            config = {
                "generation_config": {
                    "temperature": self.temperature,
                    "top_p": self.top_p,
                    "top_k": self.top_k,
                    "max_output_tokens": self.max_output_tokens
                },
                "safety_settings": [],
                "tools": self.tools
            }
        
        # Create message queues for communication with the background task
        message_queue = asyncio.Queue()
        response_queue = asyncio.Queue()
        
        # Store the session data
        self.active_sessions[session_id] = {
            "config": config,
            "message_queue": message_queue,
            "response_queue": response_queue,
            "connected": False,
            "task": None,
            "history": [],  # Initialize conversation history
            "gemini_session": None  # Will be set in the background task
        }
        
        # Initialize the response for this session
        self.session_responses[session_id] = {"text": "", "done": False, "audio": None}
        
        # Start the background task
        task = self.loop.create_task(self._session_background_task(session_id))
        self.active_sessions[session_id]["task"] = task
        
        # Log session creation
        logger.info(f"Created new session with ID: {session_id}")
        
        return session_id
        
    async def _execute_function(self, function_name, function_args):
        logger.info(f"[LiveChat] _execute_function called: {function_name} with args {function_args}")
        """Execute a function called by the Gemini API"""
        logger.info(f"Executing function {function_name} with args {function_args}")
        
        if function_name == "search_products":
            # Extract the query from the function arguments
            query = function_args.get("query")
            if not query:
                return {"error": "No query provided"}
            
            # Execute the search function
            try:
                # Make a request to the search endpoint
                async with aiohttp.ClientSession() as session:
                    search_url = f"http://localhost:5000/api/search?query={query}"
                    logger.info(f"Making search request to: {search_url}")
                    
                    async with session.get(search_url) as response:
                        if response.status == 200:
                            data = await response.json()
                            logger.info(f"Search returned {len(data.get('results', []))} results")
                            return data
                        else:
                            error_text = await response.text()
                            logger.error(f"Search failed with status {response.status}: {error_text}")
                            return {"error": f"Search failed with status {response.status}: {error_text}"}
            except Exception as e:
                logger.error(f"Error executing search_products function: {e}")
                return {"error": f"Error executing search: {str(e)}"}
        else:
            logger.warning(f"Unknown function: {function_name}")
            return {"error": f"Unknown function: {function_name}"}
    
    def get_current_response(self, session_id):
        """Get the current response for a session"""
        if session_id in self.session_responses:
            return self.session_responses[session_id]
        return None
        
    def clear_response(self, session_id):
        """Clear the response for a session after it has been retrieved"""
        if session_id in self.session_responses:
            # Don't completely remove the response, just mark it as retrieved
            # This way, we can still accumulate more text if needed
            if self.session_responses[session_id].get("done", False):
                # Only clear if the response is complete
                self.session_responses[session_id] = {"text": "", "done": False, "audio": None, "retrieved": True}
            
            logger.info(f"Cleared response for session {session_id}")
        else:
            logger.warning(f"No response to clear for session {session_id}")
    
    def get_current_audio_response(self, session_id):
        """Get the current audio response for a session"""
        if session_id not in self.active_sessions:
            return {"error": "Session not found"}
        
        # Get the current audio response from the session_audio_responses dict
        response = self.session_audio_responses.get(session_id, {})
        
        # If no response yet, return an empty response
        if not response:
            return {"text": "", "transcribed_text": "", "done": False}
        
        return response
    
    async def process_user_message(self, session_id, message):
        """Process a user message by sending it to the background task for the session"""
        # Check if the session exists
        if session_id not in self.active_sessions:
            logger.error(f"Session not found: {session_id}")
            return {"error": "Session not found"}
        
        # Add the message to the session's message queue
        logger.info(f"Received message for session {session_id}: {message[:30]}...")
        
        # Get the session's message queue
        message_queue = self.active_sessions[session_id]["message_queue"]
        
        # Put the message in the queue
        await message_queue.put(message)
        
        logger.info(f"Processing message for session {session_id}: {message[:30]}...")
        
        # Return a success response
        return {"status": "processing"}
        
    async def process_user_message_socketio(self, session_id, message_tuple, client_sid, socketio):
        """Process a user message (text + optional frame) and emit responses via Socket.IO"""
        # message_tuple is (message, frame)
        if session_id not in self.active_sessions:
            logger.error(f"Session not found: {session_id}")
            socketio.emit('error', {"error": "Session not found"}, room=client_sid)
            return
        session_data = self.active_sessions[session_id]
        if not session_data.get("connected") or session_data.get("task") is None:
            logger.error(f"Session {session_id} is not connected or background task is not running")
            socketio.emit('error', {"error": "Session not connected"}, room=client_sid)
            return
        # Store client_sid and socketio for response emission
        self.active_sessions[session_id]["client_sid"] = client_sid
        self.active_sessions[session_id]["socketio"] = socketio
        # Unpack message and frame
        if isinstance(message_tuple, tuple):
            message, frame = message_tuple
        else:
            message, frame = message_tuple, None
        # Enqueue as a tuple for the background task
        message_queue = self.active_sessions[session_id]["message_queue"]
        await message_queue.put((message, frame))
        logger.info(f"Enqueued (message, frame) for session {session_id}")
        
        # Return a success response
        return {"status": "processing"}
        
    async def end_session(self, session_id):
        """End a session and clean up resources"""
        if session_id not in self.active_sessions:
            logger.warning(f"Session not found for cleanup: {session_id}")
            return
        
        logger.info(f"Ending session {session_id}")
        
        try:
            # Get the session data
            session_data = self.active_sessions[session_id]
            
            # Signal the background task to terminate by putting None in the message queue
            await session_data["message_queue"].put(None)
            
            # Wait for the background task to complete
            if session_data.get("task") is not None:
                try:
                    await asyncio.wait_for(session_data["task"], timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout waiting for background task to complete for session {session_id}")
                    session_data["task"].cancel()
                    try:
                        await session_data["task"]
                    except asyncio.CancelledError:
                        logger.info(f"Background task for session {session_id} cancelled")
            
            # The Gemini session will be closed automatically when the background task exits
            # because we're using the async with context manager
            
            # Remove the session from active sessions
            del self.active_sessions[session_id]
            
            # Clear the response data
            if session_id in self.session_responses:
                del self.session_responses[session_id]
            
            logger.info(f"Session {session_id} ended successfully")
            
        except Exception as e:
            logger.error(f"Error ending session {session_id}: {e}")
            # Ensure the session is removed even if there's an error
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            if session_id in self.session_responses:
                del self.session_responses[session_id]
    
    async def send_user_input_to_session(self, session_id, user_input):
        """Send user input to an existing session and yield responses"""
        if session_id not in self.active_sessions:
            logger.error(f"Session not found: {session_id}")
            yield {"type": "error", "error": "Session not found"}
            return
        
        session_data = self.active_sessions[session_id]
        
        try:
            # Log the message
            logger.info(f"Sending message to session {session_id}: {user_input[:50]}...")
            
            # Create a live session if it doesn't exist
            if not session_data.get("session"):
                logger.info(f"Creating live connection for session {session_id}")
                session = await genai.aio.live.connect(
                    model=self.model_name,
                    config=session_data["config"]
                )
                session_data["session"] = session
            else:
                session = session_data["session"]
            
            # Add the message to history
            session_data["history"].append({"role": "user", "parts": [{"text": user_input}]})
            
            # Create the message content
            message_content = types.Content(
                role="user",
                parts=[types.Part(text=user_input)]
            )
            
            # Send the message to the model
            await session.send_client_content(turns=message_content, turn_complete=True)
            
            # Process the response
            accumulated_text = ""
            function_call_received = False
            
            # Receive and process the response
            async for response in session.receive():
                try:
                    # Handle text responses
                    if response.text is not None:
                        accumulated_text += response.text
                        yield {
                            "type": "text",
                            "text": response.text,
                            "done": False
                        }
                    
                    # Handle tool calls (function calls)
                    if response.tool_call and not function_call_received:
                        function_call_received = True
                        for fc in response.tool_call.function_calls:
                            logger.info(f"Received function call: {fc.name}")
                            
                            # Handle search_products function
                            if fc.name == "search_products":
                                try:
                                    # Extract query from args
                                    if hasattr(fc.args, 'get'):
                                        # Handle MapComposite object directly
                                        query = fc.args.get("query", "")
                                    else:
                                        # Handle string JSON
                                        try:
                                            args = json.loads(fc.args)
                                            query = args.get("query", "")
                                        except Exception as json_err:
                                            logger.error(f"Error parsing function args as JSON: {json_err}")
                                            query = str(fc.args)
                                    
                                    logger.info(f"Searching for products with query: {query}")
                                    
                                    # Make a request to our search API
                                    import requests
                                    response = requests.get(f"http://localhost:5000/api/search?query={query}")
                                    data = response.json()
                                    
                                    if 'results' in data:
                                        # Format the results for the model
                                        search_results = []
                                        for product in data['results'][:5]:  # Limit to 5 products for cleaner responses
                                            search_results.append({
                                                "id": product.get('id', ''),
                                                "name": product.get('name', ''),
                                                "price": product.get('price', ''),
                                                "image_url": product.get('image_url', ''),
                                                "aisle": product.get('aisle', '')
                                            })
                                    else:
                                        search_results = []
                                    
                                    # Return the search results to the client
                                    yield {
                                        "type": "function_result",
                                        "function_name": "search_products",
                                        "results": search_results
                                    }
                                    
                                    # Send the function response back to the model
                                    function_response = types.FunctionResponse(
                                        id=fc.id,
                                        name=fc.name,
                                        response={"products": search_results}
                                    )
                                    
                                    await session.send_tool_response(function_responses=[function_response])
                                except Exception as e:
                                    logger.error(f"Error processing function call: {e}")
                                    yield {"type": "error", "error": f"Error processing function call: {str(e)}"}
                    
                    # Check if generation is complete
                    if hasattr(response, 'server_content') and response.server_content:
                        if hasattr(response.server_content, 'generation_complete') and response.server_content.generation_complete:
                            logger.info(f"Generation complete for session {session_id}")
                            break
                        
                        if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                            logger.info(f"Turn complete for session {session_id}")
                            break
                    
                except Exception as e:
                    logger.error(f"Error processing response chunk: {e}")
                    yield {"type": "error", "error": f"Error processing response: {str(e)}"}
            
            # Add the complete response to history
            session_data["history"].append({"role": "assistant", "parts": [{"text": accumulated_text}]})
            
            # Generate audio for the complete response if TTS is available
            if self.tts_client and accumulated_text:
                try:
                    synthesis_input = texttospeech.SynthesisInput(text=accumulated_text)
                    response = self.tts_client.synthesize_speech(
                        input=synthesis_input,
                        voice=self.voice,
                        audio_config=self.audio_config
                    )
                    
                    # Encode the audio content as base64
                    audio_content = base64.b64encode(response.audio_content).decode('utf-8')
                    
                    # Yield the audio response
                    yield {
                        "type": "audio",
                        "audio": audio_content
                    }
                except Exception as e:
                    logger.error(f"Error generating audio: {e}")
            
            # Signal that the interaction is complete
            yield {
                "type": "text",
                "text": "",
                "done": True
            }
            
            yield {
                "type": "status",
                "status": "ended"
            }
        
        except Exception as e:
            logger.error(f"Error in send_user_input_to_session: {e}")
            yield {"type": "error", "error": f"Error processing request: {str(e)}"}

    def handle_video_frame(self, session_id, frame_data_url):
        """Handle a video frame sent from the client in LiveChat mode."""
        logger.info(f"[LiveChat] handle_video_frame called for session {session_id}")
        if session_id not in self.active_sessions:
            logger.error(f"[LiveChat] Session not found: {session_id}")
            return
        try:
            # Parse the data URL
            header, encoded = frame_data_url.split(",", 1)
            mime_type = header.split(":")[1].split(";")[0] if ":" in header and ";" in header else "image/jpeg"
            frame_bytes = base64.b64decode(encoded)
            # Create a Gemini Part for the image
            part = Part.from_bytes(data=frame_bytes, mime_type=mime_type)
            # Enqueue the image part to the session's message queue
            message_queue = self.active_sessions[session_id]["message_queue"]
            self.loop.call_soon_threadsafe(message_queue.put_nowait, part)
            logger.info(f"[LiveChat] Video frame enqueued for session {session_id}")
        except Exception as e:
            logger.error(f"[LiveChat] Error handling video frame for session {session_id}: {e}")

    async def stream_tts_audio(self, session_id, text, socketio, client_sid):
        """Stream TTS audio chunks to the client for playback (modular, ADA-style)."""
        if not self.tts_client or not text:
            return
        try:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            tts_response = self.tts_client.synthesize_speech(
                input=synthesis_input,
                voice=self.voice,
                audio_config=self.audio_config
            )
            audio_bytes = tts_response.audio_content
            # Simulate chunking (e.g., 4KB per chunk)
            chunk_size = 4096
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i:i+chunk_size]
                audio_b64 = base64.b64encode(chunk).decode('utf-8')
                socketio.emit('receive_audio_chunk', {'audio': audio_b64}, room=client_sid)
            socketio.emit('audio_stream_end', {}, room=client_sid)
        except Exception as e:
            logger.error(f"Error streaming TTS audio: {e}")
