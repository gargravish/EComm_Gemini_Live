import os
import json
import logging
from dotenv import load_dotenv
from flask import Flask, request, jsonify, Response, stream_with_context, make_response
from flask_cors import CORS
from flask_socketio import SocketIO, emit, Namespace
import concurrent.futures
import threading
import asyncio
from bigquery_service import BigQueryService
from vertex_ai_service import VertexAIService
import time
import re
import random
from queue import Queue
from utils import normalize_product
from gemini_live2_service import GeminiLive2Service

# Configure logging to file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=[
        logging.FileHandler('server.log', mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import our services
from gemini_multimodal_service import GeminiMultimodalService
from gemini_live_service import GeminiLiveService

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Set app secret key
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'a_default_fallback_secret_key!')

# Initialize Socket.IO
REACT_APP_PORT = os.getenv('REACT_APP_PORT', '5173')
REACT_APP_ORIGIN = f"http://localhost:{REACT_APP_PORT}"
REACT_APP_ORIGIN_IP = f"http://127.0.0.1:{REACT_APP_PORT}"

# Get allowed origins from environment variables or use defaults
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', f'{REACT_APP_ORIGIN},{REACT_APP_ORIGIN_IP},http://localhost:3000,http://127.0.0.1:3000')
allowed_origins = CORS_ALLOWED_ORIGINS.split(',')

# Initialize Socket.IO with proper configuration
socketio = SocketIO(
    app,
    async_mode='threading',  # Keep threading mode as it's already working
    cors_allowed_origins=allowed_origins,
    logger=True,  # Enable Socket.IO logger
    engineio_logger=True,  # Enable Engine.IO logger
    ping_timeout=60,  # Increase ping timeout
    ping_interval=25,  # Adjust ping interval
    max_http_buffer_size=1e8  # Increase buffer size for large messages
)

# Add default error handler for Socket.IO
@socketio.on_error_default
def default_error_handler(e):
    logger.error(f"SocketIO error: {e}", exc_info=True)

# Configure CORS
REACT_APP_PORT = os.getenv('REACT_APP_PORT', '5173')
REACT_APP_ORIGIN = f"http://localhost:{REACT_APP_PORT}"
REACT_APP_ORIGIN_IP = f"http://127.0.0.1:{REACT_APP_PORT}"

# Use a more permissive CORS configuration for development
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Asyncio event loop for background tasks
background_loop = asyncio.new_event_loop()

def run_asyncio_loop(loop):
    """Function to run the asyncio event loop in a separate thread"""
    asyncio.set_event_loop(loop)
    try:
        print("Asyncio event loop started...")
        loop.run_forever()
    finally:
        print("Asyncio event loop stopping...")
        tasks = asyncio.all_tasks(loop=loop)
        for task in tasks:
            if not task.done():
                task.cancel()
        try:
            loop.run_until_complete(asyncio.gather(*[t for t in tasks if not t.done()], return_exceptions=True))
            loop.run_until_complete(loop.shutdown_asyncgens())
        except RuntimeError as e:
            print(f"RuntimeError during loop cleanup (might be expected if loop stopped abruptly): {e}")
        except Exception as e:
            print(f"Exception during loop cleanup: {e}")
        finally:
            if not loop.is_closed():
                loop.close()
        print("Asyncio event loop stopped.")

# Start the background thread for asyncio
background_thread = concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(run_asyncio_loop, background_loop)

# Initialize services
gemini_multimodal_service = GeminiMultimodalService()
gemini_live_service = GeminiLiveService(loop=background_loop) # Pass the loop
gemini_live2_service = GeminiLive2Service(loop=background_loop)

# Thread pool for async operations
executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

# Helper function for CORS preflight requests
def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
    return response

# Helper function to schedule user message processing
def _schedule_process_user_message(session_id, message):
    # Use the application's background_loop for scheduling async tasks
    asyncio.run_coroutine_threadsafe(
        gemini_live_service.process_user_message(session_id, message),
        background_loop  # Use the application's background loop instead of gemini_live_service.loop
    )

# API Routes for Gemini Multimodal
@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle regular chat messages using Gemini Multimodal API"""
    data = request.json
    message = data.get('message', '')
    history = data.get('history', [])
    
    response = gemini_multimodal_service.generate_content(message, history)
    return jsonify(response)

# Search endpoint moved to the bottom of the file with BigQuery and Vertex AI integration

@app.route('/api/chat/image', methods=['POST'])
def chat_with_image():
    """Handle chat with image using Gemini Multimodal API"""
    data = request.json
    message = data.get('message', '')
    image_data = data.get('image', '')
    history = data.get('history', [])
    
    response = gemini_multimodal_service.generate_content_with_image(message, image_data, history)
    return jsonify(response)

# API Routes for Gemini Live
@app.route('/api/live/start', methods=['POST'])
def start_live_session():
    """Start a new Gemini Live session"""
    # This will be an async operation
    def generate():
        async def create_session():
            try:
                session_id = await gemini_live_service.create_session()
                return session_id
            except Exception as e:
                logger.error(f"Error creating live session: {e}")
                return None
        
        # Create the coroutine object
        coro = create_session()
        
        # Run the async function in the background loop and wait for results
        future = asyncio.run_coroutine_threadsafe(coro, background_loop)
        try:
            # Wait for the coroutine to complete and get the session ID
            session_id = future.result()
            if session_id:
                return jsonify({"session_id": session_id})
            else:
                return jsonify({"error": "Failed to create session"}), 500
        except Exception as e:
            logger.error(f"Error in start_live_session: {e}")
            return jsonify({"error": f"Error creating session: {str(e)}"}), 500
    
    return generate()

@app.route('/api/live/message', methods=['POST', 'OPTIONS'])
def send_live_message():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        message = data.get('message')
        
        if not session_id or not message:
            return jsonify({'error': 'session_id and message are required'}), 400

        app.logger.info(f"Received message for session {session_id}: {message[:30]}...")
                
        # Process the message in a new thread using the scheduler
        thread = threading.Thread(target=_schedule_process_user_message, args=(session_id, message))
        thread.start()
        
        return jsonify({'message': 'Message received, processing...'}), 202

    except Exception as e:
        app.logger.error(f"Error in send_live_message: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/live/response/<session_id>', methods=['GET'])
def get_live_response(session_id):
    # Retrieve the current response for the session_id
    response_content = gemini_live_service.get_current_response(session_id)
    if response_content:
        # Clear the response after retrieving it
        gemini_live_service.clear_response(session_id)
        return jsonify(response_content)
    else:
        return jsonify({'status': 'processing'}), 202

@app.route('/api/live/end', methods=['POST'])
def end_live_session():
    """End a Gemini Live session"""
    data = request.json
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({"error": "No session_id provided"}), 400
    
    # This will be an async operation
    def generate():
        async def close_session():
            try:
                success = await gemini_live_service.end_session(session_id)
                return success
            except Exception as e:
                logger.error(f"Error ending live session: {e}")
                return False
        
        # Create the coroutine object
        coro = close_session()
        
        # Run the async function in the background loop and wait for results
        future = asyncio.run_coroutine_threadsafe(coro, background_loop)
        try:
            # Wait for the coroutine to complete and get the result
            success = future.result()
            if success:
                return jsonify({"status": "success", "message": "Session ended"})
            else:
                return jsonify({"error": "Failed to end session"}), 404
        except Exception as e:
            logger.error(f"Error in end_live_session: {e}")
            return jsonify({"error": f"Error ending session: {str(e)}"}), 500
    
    return generate()

# API Routes for Gemini Live2 (VAD+Camera+Audio)
@app.route('/api/live2/start', methods=['POST'])
def start_live2_session():
    """Start a new Gemini Live2 session"""
    session_id = gemini_live2_service.create_session()
    return jsonify({"session_id": session_id})

@app.route('/api/live2/message', methods=['POST', 'OPTIONS'])
def send_live2_message():
    """Send a message or media chunk to a Live2 session"""
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    # Accept JSON: { session_id, audio (base64 or bytes) }
    data = request.get_json()
    session_id = data.get('session_id')
    audio_b64 = data.get('audio')
    import base64
    if not session_id or not audio_b64:
        return jsonify({"error": "session_id and audio are required"}), 400
    try:
        pcm_bytes = base64.b64decode(audio_b64)
    except Exception as e:
        return jsonify({"error": f"Invalid audio encoding: {e}"}), 400
    result = gemini_live2_service.handle_audio_chunk(session_id, pcm_bytes)
    return jsonify(result)

@app.route('/api/live2/end', methods=['POST'])
def end_live2_session():
    """End a Gemini Live2 session"""
    data = request.get_json()
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    success = gemini_live2_service.end_session(session_id)
    return jsonify({"status": "ended" if success else "not found"})

@app.route('/api/search', methods=['GET', 'POST'])
def search():
    """Handle search requests for products using BigQuery and Vertex AI"""
    try:
        # Handle both GET and POST requests
        if request.method == 'POST':
            data = request.json
            if not data:
                return jsonify({'error': 'No search data provided'}), 400
            query = data.get('query')
            image_data = data.get('image_data')
            neighbor_count = data.get('neighbor_count', 10)
        else:  # GET method
            query = request.args.get('query')
            image_data = None  # Image data should only be sent via POST
            neighbor_count = int(request.args.get('neighbor_count', 10))
        logger.info(f"/api/search {request.method} received: query={query}, image_data={'yes' if image_data else 'no'}")
        
        if not query and not image_data:
            return jsonify({'error': 'Either query or image_data must be provided'}), 400
        
        # Get configuration from environment variables
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        region = os.getenv('VERTEX_AI_LOCATION')
        feature_store_id = os.getenv('FEATURE_STORE_ID')
        feature_view_id = os.getenv('ENTITY_TYPE_ID')
        dataset = os.getenv('BIGQUERY_DATASET')
        
        # Validate required configuration
        if not project_id or not region or not feature_store_id or not feature_view_id or not dataset:
            return jsonify({
                'error': 'Google Cloud configuration is incomplete',
                'details': 'Please check your environment variables for Google Cloud, Vertex AI, and BigQuery settings.'
            }), 500
        
        start_time = time.time()
        
        # Initialize services
        vertex_service = VertexAIService(
            project_id=project_id,
            location=region,
            feature_store_id=feature_store_id,
            feature_view_id=feature_view_id
        )
        
        bigquery_service = BigQueryService(
            project_id=project_id,
            dataset=dataset
        )
        
        # Generate embeddings
        t0 = time.time()
        embeddings = vertex_service.get_image_embeddings(
            image_data=image_data,
            contextual_text=query
        )
        t1 = time.time()
        logger.info(f"Embeddings generated in {t1-t0:.2f} seconds")
        
        # Search feature store
        t2 = time.time()
        search_results = vertex_service.search_feature_store(
            embedding=embeddings,
            neighbor_count=neighbor_count
        )
        t3 = time.time()
        logger.info(f"Feature store search in {t3-t2:.2f} seconds")
        
        if not search_results:
            return jsonify({
                'results': [],
                'message': 'No matching products found',
                'elapsed_time': time.time() - start_time
            })
        
        # Extract GCS URIs and product IDs
        gcs_uri_list = [result['gcs_uri'] for result in search_results]
        product_id_list = [result['product_id'] for result in search_results]
        
        # Parallelize BigQuery calls
        t4 = time.time()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_signed_urls = executor.submit(bigquery_service.get_signed_urls, gcs_uri_list)
            future_product_info = executor.submit(bigquery_service.get_product_info, product_id_list)
            signed_urls = future_signed_urls.result()
            product_info = future_product_info.result()
        t5 = time.time()
        logger.info(f"BigQuery get_signed_urls + get_product_info in {t5-t4:.2f} seconds")
        
        # Combine results (optimize product info lookup)
        t6 = time.time()
        product_info_dict = {str(info['productid']): info for info in product_info}
        results = []
        for i, (product_id, signed_url) in enumerate(zip(product_id_list, signed_urls)):
            product_info_item = product_info_dict.get(product_id)
            product = {
                'id': product_id,
                'image_url': signed_url,
                'name': f"Product {product_id}",
                'description': f"This product matches your {query if query else 'image'} search",
                'price': f"${random.randint(999, 9999)/100:.2f}",
                'aisle': product_info_item['aisle'] if product_info_item else 'Unknown'
            }
            results.append(normalize_product(product, query=query))
        t7 = time.time()
        logger.info(f"Product info match + normalization in {t7-t6:.2f} seconds")

        elapsed_time = time.time() - start_time
        logger.info(f"Total /api/search time (just before response): {elapsed_time:.2f} seconds")
        
        return jsonify({
            'results': results,
            'elapsed_time': elapsed_time
        })
            
    except Exception as e:
        print(f"Error in search endpoint: {str(e)}")
        return jsonify({
            'error': 'Search failed',
            'details': str(e)
        }), 500

# Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    logger.info(f"Client connected: {request.sid}")
    logger.info(f"Transport: {request.environ.get('HTTP_UPGRADE', 'polling')}")
    emit('status', {'message': 'Connected to server'}, room=request.sid)
    logger.info(f"Sent status message to client: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect(sid):
    logger.info(f"Client disconnected: {sid}")

@socketio.on('start_session')
def handle_start_session():
    try:
        client_sid = request.sid  # Capture the client SID here
        # Schedule the coroutine in the background loop and get a future
        future = asyncio.run_coroutine_threadsafe(
            gemini_live_service.create_session(),
            background_loop
        )
        # Wait for the result
        session_id = future.result(timeout=10)
        logger.info(f"Created new session with ID: {session_id} for client: {client_sid}")
        emit('session_created', {'session_id': session_id}, room=client_sid)
        # No session_ready wait; allow messages immediately
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        emit('error', {'message': f"Error creating session: {str(e)}"}, room=request.sid)

@socketio.on('send_message')
def handle_send_message(data):
    session_id = data.get('session_id')
    message = data.get('message')
    frame = data.get('frame')
    client_sid = request.sid
    logger.info(f"[LiveChat] Received send_message: session_id={session_id}, message={message[:30] if message else ''}, frame={'yes' if frame else 'no'}")
    if not session_id or not message:
        emit('error', {'message': 'session_id and message are required'}, room=client_sid)
        return
    # Enqueue both text and frame as a tuple for a single user turn
    asyncio.run_coroutine_threadsafe(
        gemini_live_service.process_user_message_socketio(session_id, (message, frame), client_sid, socketio),
        background_loop
    )

@socketio.on('end_session')
def handle_end_session(data):
    try:
        session_id = data.get('session_id')
        
        if not session_id:
            emit('error', {'message': 'session_id is required'}, room=request.sid)
            return
        
        # Schedule the coroutine in the background loop
        future = asyncio.run_coroutine_threadsafe(
            gemini_live_service.end_session(session_id),
            background_loop
        )
        # Wait for the result
        future.result(timeout=10)
        logger.info(f"Ended session with ID: {session_id}")
        emit('session_ended', {'session_id': session_id}, room=request.sid)
    except Exception as e:
        logger.error(f"Error ending session: {e}")
        emit('error', {'message': f"Error ending session: {str(e)}"}, room=request.sid)

# Helper function to process user messages and emit responses via Socket.IO
def _schedule_process_user_message_socketio(session_id, message, client_sid):
    try:
        # Schedule the task in the asyncio event loop
        future = asyncio.run_coroutine_threadsafe(
            gemini_live_service.process_user_message_socketio(session_id, message, client_sid, socketio),
            background_loop
        )
        # Wait for the result (optional)
        result = future.result(timeout=30)
        return result
    except Exception as e:
        logger.error(f"Error scheduling message processing: {e}")
        socketio.emit('error', {'message': f"Error processing message: {str(e)}"}, room=client_sid)

@socketio.on('video_frame')
def handle_video_frame(data):
    logger.info(f"[Live2] handle_video_frame event received: {data}")
    session_id = data.get('session_id')
    frame_data_url = data.get('frame')
    if not session_id or not frame_data_url:
        emit('error', {'message': 'session_id and frame are required'}, room=request.sid)
        return
    gemini_live2_service.handle_video_frame(session_id, frame_data_url)
    logger.info(f"[Live2] Received video frame for session {session_id}, length={len(frame_data_url)} (default namespace)")
    # Optionally emit an ack or status

@socketio.on('video_feed_stopped')
def handle_video_feed_stopped(data):
    session_id = data.get('session_id')
    if not session_id:
        emit('error', {'message': 'session_id is required'}, room=request.sid)
        return
    gemini_live2_service.clear_video_queue(session_id)
    logger.info(f"[Live2] Cleared video frame queue for session {session_id} (video_feed_stopped event)")
    emit('video_queue_cleared', {'session_id': session_id}, room=request.sid)

class Live2Namespace(Namespace):
    def on_connect(self):
        logger.info(f"[Live2] Client connected: {request.sid}")
        emit('status', {'message': 'Connected to Live2'}, room=request.sid)

    def on_disconnect(self, *args, **kwargs):
        logger.info(f"[Live2] Client disconnected: {request.sid}")
        # TODO: Clean up session if needed

    def on_start_live2_session(self, data=None):
        # Start a new Gemini Live2 session
        session_id = gemini_live2_service.create_session()
        gemini_live2_service.set_socketio(session_id, socketio, request.sid)
        # Start async streaming in background loop
        future = asyncio.run_coroutine_threadsafe(
            gemini_live2_service.process_streaming(session_id),
            background_loop
        )
        gemini_live2_service.sessions[session_id]["stream_task"] = future
        logger.info(f"[Live2] Started session {session_id} for client {request.sid}")
        emit('live2_session_started', {'session_id': session_id}, room=request.sid)

    def on_audio_chunk(self, data):
        # Receive audio chunk from client and forward to Gemini
        import base64
        session_id = data.get('session_id')
        audio_b64 = data.get('audio')
        if not session_id or not audio_b64:
            emit('error', {'message': 'session_id and audio are required'}, room=request.sid)
            return
        try:
            pcm_bytes = base64.b64decode(audio_b64)
        except Exception as e:
            emit('error', {'message': f'Invalid audio encoding: {e}'}, room=request.sid)
            return
        gemini_live2_service.handle_audio_chunk(session_id, pcm_bytes)
        emit('live2_audio_ack', {'status': 'received'}, room=request.sid)

    def on_video_frame(self, data):
        # Receive video frame from client and forward to Gemini
        session_id = data.get('session_id')
        frame_data_url = data.get('frame')  # This should be the full data URL
        if not session_id or not frame_data_url:
            emit('error', {'message': 'session_id and frame are required'}, room=request.sid)
            return
        gemini_live2_service.handle_video_frame(session_id, frame_data_url)
        logger.info(f"[Live2] Received video frame for session {session_id}, length={len(frame_data_url)}")
        # Optionally emit an ack or status

    def on_end_live2_session(self, data):
        session_id = data.get('session_id')
        gemini_live2_service.end_session(session_id)
        logger.info(f"[Live2] Ended session {session_id}")
        emit('live2_session_ended', {'session_id': session_id}, room=request.sid)

# Register the namespace
socketio.on_namespace(Live2Namespace('/live2'))

# Example: log all incoming HTTP requests
@app.before_request
def log_request_info():
    logger.info(f"HTTP {request.method} {request.path} - args: {request.args} - form: {request.form}")

# Example: log unhandled exceptions
def log_exception(sender, exception, **extra):
    logger.error(f"Unhandled Exception: {exception}", exc_info=True)
app.logger.handlers = logger.handlers
app.logger.setLevel(logging.INFO)
try:
    from flask import got_request_exception
    got_request_exception.connect(log_exception, app)
except Exception:
    pass

@app.route('/debug', methods=['GET'])
def debug_status():
    """Diagnostic endpoint for health and session status."""
    try:
        status = {
            "live2": gemini_live2_service.get_status(),
            "live": getattr(gemini_live_service, 'get_status', lambda: 'not_implemented')(),
            "multimodal": 'ok',
            "bigquery": 'ok',
            "vertexai": 'ok',
        }
        return jsonify({"status": "ok", "details": status})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

@app.route('/check-assets', methods=['GET'])
def check_assets():
    """Diagnostic endpoint to check static asset availability."""
    try:
        # Example: check if a frontend asset exists (customize as needed)
        asset_path = os.path.join(os.path.dirname(__file__), '../client/src/public/favicon.ico')
        exists = os.path.exists(asset_path)
        return jsonify({"favicon_exists": exists})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

@socketio.on('send_video_frame')
def handle_send_video_frame(data):
    session_id = data.get('session_id')
    frame_data_url = data.get('frame')
    logger.info(f"[LiveChat] Received video frame for session {session_id}, length={len(frame_data_url) if frame_data_url else 0}")
    if not session_id or not frame_data_url:
        emit('error', {'message': 'session_id and frame are required'}, room=request.sid)
        return
    # Forward to gemini_live_service for LiveChat
    gemini_live_service.handle_video_frame(session_id, frame_data_url)

if __name__ == '__main__':
    print("Starting Flask-SocketIO server...")
    import eventlet
    import eventlet.wsgi
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
