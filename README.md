# MD Audible

Convert markdown chapter files (`.md`) into speech audio using OpenRouter model `openai/gpt-audio-mini`.

## Stack
- Frontend: Vite + React + TypeScript
- Backend: FastAPI + Python

## Project structure
- `frontend/`: React UI for upload, voice selection, conversion, and playback
- `backend/`: FastAPI API that receives `.md`, calls OpenRouter TTS, and stores generated audio under `backend/audio/`

## Backend setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# add OPENROUTER_API_KEY to .env
uvicorn main:app --reload --port 8000
```

## Frontend setup
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Frontend runs on `http://localhost:5173` and API on `http://localhost:8000`.

## API
- `POST /api/convert` form-data:
  - `markdown_file`: `.md` file
  - `voice`: one of `alloy`, `nova`, `onyx`, `echo`, `fable`, `shimmer`
- Returns JSON:
  - `filename`
  - `audio_url` (served from `/audio/<name>.mp3`)
