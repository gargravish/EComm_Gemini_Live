# Project Plan: RavMart Assistant (Semantic_Search_New)

## Overview
RavMart Assistant is a modern conversational assistant application with two primary modes:
- **Gemini Multimodal API**: Text and image-based conversations, product search, and markdown rendering.
- **Gemini Live API**: Real-time, streaming conversations with audio support, including text-to-speech and session management.

The project is organized into a clear client-server architecture:
- **Frontend**: React (TypeScript, Vite, Material UI)
- **Backend**: Python (Flask), Google Gemini API, Vertex AI, BigQuery, and Google Cloud services

---

## Technology Stack

### Frontend
- **React** (TypeScript)
- **Vite** (build tool)
- **Material UI** (UI components)
- **Axios** (API requests)
- **React Markdown** (markdown rendering)
- **Socket.IO Client** (real-time communication)

### Backend
- **Python 3**
- **Flask** (web server)
- **Flask-CORS** (CORS support)
- **Flask-SocketIO** (real-time streaming)
- **Google Gemini API** (LLM, multimodal, and live streaming)
- **Google Cloud Text-to-Speech**
- **Google Cloud BigQuery** (product data, embeddings)
- **Google Cloud Storage** (image hosting)
- **Vertex AI** (image/text embeddings, feature store)
- **python-dotenv** (environment variable management)
- **Pillow** (image processing)

---

## Directory Structure

```
Semantic_Search_New/
├── client/               # React frontend
│   └── src/              # React application
│       ├── src/          # Source code
│       │   ├── components/  # React components
│       │   ├── App.tsx   # Main application component
│       │   └── ...       # Other React files
│       └── ...           # Configuration files
└── server/               # Flask backend
    ├── app.py            # Main Flask application
    ├── gemini_live_service.py      # Gemini Live API service
    ├── gemini_multimodal_service.py # Gemini Multimodal API service
    ├── gemini_tool_definitions.py  # Tool definitions for Gemini
    ├── bigquery_service.py         # BigQuery integration
    ├── vertex_ai_service.py        # Vertex AI integration
    ├── utils.py                    # Utility functions
    ├── requirements.txt            # Python dependencies
    └── run.py                      # Server entry point
```

---

## Key Backend Components & Functions

### 1. **app.py** (Flask Entrypoint)
- Loads environment variables and configures Flask, CORS, and Socket.IO.
- Initializes GeminiMultimodalService and GeminiLiveService.
- **API Endpoints:**
  - `/api/chat` (POST): Text chat via Gemini Multimodal
  - `/api/chat/image` (POST): Chat with image via Gemini Multimodal
  - `/api/live/start` (POST): Start a live session
  - `/api/live/message` (POST): Send message to live session
  - `/api/live/audio` (POST): Send audio to live session
  - `/api/live/end` (POST): End live session
  - `/api/search` (POST/GET): Product search (text/image)
- **Socket.IO Events:**
  - `connect`, `disconnect`, `start_session`, `send_message`, `end_session`, etc.
- **Configuration Variables Used:**
  - `FLASK_SECRET_KEY`, `REACT_APP_PORT`, `CORS_ALLOWED_ORIGINS`

### 2. **gemini_multimodal_service.py**
- Handles all Gemini Multimodal API interactions.
- **Key Functions:**
  - `generate_content(message, history)`: Generates LLM response for text.
  - `generate_content_with_image(message, image_data, history)`: Handles image+text queries.
  - `_process_function_call(function_call)`: Handles tool/function calls (e.g., product search).
- **Configuration Variables Used:**
  - `GEMINI_API_KEY`, `GEMINI_MULTIMODAL_MODEL`, `GEMINI_TEMPERATURE`, `GEMINI_TOP_P`, `GEMINI_TOP_K`, `GEMINI_MAX_OUTPUT_TOKENS`, `GEMINI_MULTIMODAL_INSTRUCTIONS`

### 3. **gemini_live_service.py**
- Handles Gemini Live API for real-time streaming and audio.
- **Key Functions:**
  - `create_session()`: Starts a new live session.
  - `process_user_message(session_id, message)`: Handles incoming messages.
  - `end_session(session_id)`: Ends a live session.
  - Text-to-speech streaming using Google Cloud TTS.
- **Configuration Variables Used:**
  - `GEMINI_API_KEY`, `GEMINI_LIVE_MODEL`, `TTS_LANGUAGE_CODE`, `TTS_VOICE_NAME`, `TTS_AUDIO_ENCODING`, `GEMINI_TEMPERATURE`, `GEMINI_TOP_P`, `GEMINI_TOP_K`, `GEMINI_MAX_OUTPUT_TOKENS`, `GEMINI_LIVE_INSTRUCTIONS`

### 4. **bigquery_service.py**
- Integrates with Google BigQuery and Cloud Storage for product search and image URLs.
- **Key Functions:**
  - `get_signed_urls(urls)`: Generates signed URLs for images.
  - `get_product_info(product_ids)`: Fetches product metadata.
  - `search_products(embeddings, k)`: Embedding-based product search.
- **Configuration Variables Used:**
  - Project and dataset IDs (from environment or code)

### 5. **vertex_ai_service.py**
- Integrates with Vertex AI for image/text embeddings and feature store search.
- **Key Functions:**
  - `get_image_embeddings(image_data, contextual_text)`: Generates embeddings.
  - `search_feature_store(embedding, neighbor_count)`: Finds similar products.
- **Configuration Variables Used:**
  - Project, location, feature store/view IDs

### 6. **gemini_tool_definitions.py**
- Defines tools (functions) for Gemini API, e.g., `search_products`.

### 7. **utils.py**
- Utility: `normalize_product(product, query)` ensures product dicts have required fields.

---

## Key Frontend Components & Functions

### 1. **App.tsx**
- Main application shell, theme, and layout.
- Handles tab switching, search, and chat assistant modal.
- Integrates with backend via fetch/axios for search and chat.

### 2. **components/**
- **MultimodalChat.tsx**: Handles chat UI for text/image, calls `/api/chat` and `/api/chat/image`.
- **LiveChat.tsx**: Real-time chat with streaming, uses Socket.IO for `/api/live` endpoints.
- **ImageUpload.tsx**: Drag-and-drop or file upload, sends image to `/api/search`.
- **ProductResults.tsx**: Renders product search results.
- **SearchBar.tsx**: Search input for products.
- **RavMartAssistant.tsx**: Assistant UI.

### 3. **vite.config.ts**
- Proxies `/api` requests to backend (`http://localhost:5000`).
- Asset paths and base can be configured here for deployment.

---

## Environment Variables (Non-Sensitive)
- `REACT_APP_PORT`: Port for React dev server (default: 5173)
- `FLASK_SECRET_KEY`: Flask session secret (do not commit real value)
- `GEMINI_API_KEY`: Gemini API key (do not commit real value)
- `GEMINI_MULTIMODAL_MODEL`, `GEMINI_LIVE_MODEL`: Model names for Gemini APIs
- `GEMINI_TEMPERATURE`, `GEMINI_TOP_P`, `GEMINI_TOP_K`, `GEMINI_MAX_OUTPUT_TOKENS`: LLM generation parameters
- `TTS_LANGUAGE_CODE`, `TTS_VOICE_NAME`, `TTS_AUDIO_ENCODING`: TTS config
- Project, dataset, and feature store IDs for GCP services

---

## Library/Dependency List

### Backend (from requirements.txt)
- flask, flask-cors, flask-socketio
- python-dotenv
- google-generativeai
- google-cloud-texttospeech
- google-cloud-bigquery
- google-cloud-storage
- vertexai
- pillow
- google-cloud-aiplatform
- asyncio

### Frontend (from package.json)
- react, react-dom, @mui/material, @mui/icons-material, @emotion/react, @emotion/styled
- axios
- react-markdown
- react-router-dom
- socket.io-client
- vite, typescript, eslint, etc. (dev)

---

## Connectivity & Data Flow

1. **User interacts with frontend (React, Material UI)**
   - Product search (text/image) → `/api/search` (POST)
   - Multimodal chat → `/api/chat` or `/api/chat/image`
   - Live chat (streaming) → Socket.IO events and `/api/live/*` endpoints

2. **Backend (Flask) routes requests:**
   - For chat: Uses GeminiMultimodalService (LLM)
   - For live: Uses GeminiLiveService (LLM streaming, TTS)
   - For product search: Uses VertexAIService (embeddings) and BigQueryService (product data)

3. **Data sources:**
   - Product data and embeddings in BigQuery
   - Images in Google Cloud Storage
   - Embedding search via Vertex AI Feature Store

4. **LLM Integration:**
   - Gemini API is used for all AI/LLM tasks (text, image, streaming)
   - Tool/function calls (e.g., product search) are handled via Gemini's function calling

5. **Frontend renders results:**
   - Product cards, markdown chat, streaming responses, and audio playback

---

## Security & Best Practices
- All sensitive config (API keys, secrets) must be in `.env` files (never hardcoded or committed)
- CORS and Socket.IO origins are restricted/configurable
- User input is validated and sanitized on backend
- Google IAM roles and service accounts should be least-privilege
- Diagnostic endpoints and error handling are present for debugging

---

## For Future Enhancements
- This document provides a full map of the current architecture, data flow, and key integration points.
- For any new features, ensure:
  - Environment variables are added to `.env.example` and documented
  - New endpoints or services are added to this plan
  - LLM prompt/response formats are updated here if changed
- All enhancements should follow the existing patterns for separation of concerns, security, and scalability.

---

## References
- See `README.md` for setup and usage instructions
- See `requirements.txt` and `package.json` for full dependency lists
- See `vite.config.ts` for frontend asset and proxy configuration 