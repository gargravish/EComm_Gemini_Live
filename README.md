# RavMart Assistant (E-Comm Gemini Live)

A modern conversational assistant application with two distinct modes:

1. **Gemini Multimodal API** - For text and image-based conversations
2. **Gemini Live API** - For real-time, streaming conversations with audio support

---

## Project Structure

```
EComm_Gemini_Live/
├── client/               # React + Vite frontend (TypeScript, Material UI)
│   ├── src/              # Main source code
│   │   ├── components/   # React components
│   │   ├── App.tsx       # Main app shell
│   │   └── ...           # Other React files
│   ├── public/           # Static assets
│   ├── package.json      # Frontend dependencies
│   └── ...               # Config files, node_modules, etc.
├── server/               # Python Flask backend
│   ├── app.py            # Main Flask app
│   ├── gemini_live_service.py      # Gemini Live API service
│   ├── gemini_multimodal_service.py # Gemini Multimodal API service
│   ├── gemini_tool_definitions.py  # Gemini tool definitions
│   ├── bigquery_service.py         # BigQuery integration
│   ├── vertex_ai_service.py        # Vertex AI integration
│   ├── utils.py                    # Utility functions
│   ├── requirements.txt            # Python dependencies
│   └── run.py                      # Server entry point
├── project_plan.md      # Project plan and architecture
├── README.md            # Main documentation
├── .gitignore           # Git ignore rules
└── .env.example         # Example environment variables (root-level)
```

---

## Features

### Multimodal Mode
- Text-based conversations
- Image upload and analysis
- Product search functionality
- Markdown rendering for responses

### Live Mode
- Real-time streaming responses
- Audio input via microphone
- Text-to-speech output
- Session management

---

## Setup Instructions

### Environment Configuration

1. Copy `.env.example` in the project root to `.env` and fill in the required values:
   ```bash
   cp .env.example .env
   # Edit .env to add your secrets and configuration
   ```

### Backend Setup

1. Navigate to the server directory:
   ```bash
   cd server
   ```
2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the Flask server:
   ```bash
   python run.py
   ```

### Frontend Setup

1. Navigate to the client directory:
   ```bash
   cd client
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
4. Open your browser and navigate to:
   ```
   http://localhost:5173
   ```

---

## API Endpoints

### Multimodal API
- `POST /api/chat` - Send a text message
- `POST /api/chat/image` - Send a message with an image

### Live API
- `POST /api/live/start` - Start a new live session
- `POST /api/live/message` - Send a message to a live session
- `POST /api/live/audio` - Send audio to a live session
- `POST /api/live/end` - End a live session

---

## Environment Variables

All environment variables must be set in the root-level `.env` file. **Never commit your real .env file.**

### Example .env.example (root-level)
```
# Gemini & Flask
GEMINI_API_KEY=your_gemini_api_key
FLASK_SECRET_KEY=your_secret_key
REACT_APP_PORT=5173
GEMINI_MULTIMODAL_MODEL=gemini-1.5-flash
GEMINI_LIVE_MODEL=gemini-1.5-flash
GEMINI_TEMPERATURE=0.2
GEMINI_TOP_P=1.0
GEMINI_TOP_K=32
GEMINI_MAX_OUTPUT_TOKENS=2048
TTS_LANGUAGE_CODE=en-US
TTS_VOICE_NAME=en-US-Standard-B
TTS_AUDIO_ENCODING=MP3
GCP_PROJECT_ID=your_project_id
GCP_DATASET_ID=your_dataset_id
GCP_FEATURESTORE_ID=your_featurestore_id
GCP_LOCATION=us-central1

# Frontend
VITE_API_URL=http://localhost:5000
```

---

## Security & Best Practices
- All secrets and API keys must be stored in `.env` files (never hardcoded).
- Use Google Secret Manager for production secrets.
- Use least-privilege IAM roles for backend services.
- Configure Content Security Policy (CSP) for frontend.

---

## Testing & Debugging
- Add unit tests for backend (pytest) and frontend (Jest/React Testing Library).
- Diagnostic endpoints: `/debug`, `/check-assets`, `/static-test`.
- Use integration tests for API and UI.

---

## Files That Can Be Safely Removed
- `.DS_Store` (all locations)
- `server/__pycache__/` (all contents)
- `server/server.log`
- `client/.DS_Store`

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.
