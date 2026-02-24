import os
from datetime import datetime
import math
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
load_dotenv(BASE_DIR / ".env")

SUPPORTED_VOICES = ["alloy", "nova", "onyx", "echo", "fable", "shimmer"]
SAMPLE_DEFAULT_TEXT = (
    "This is a sample of the selected voice. "
    "It is designed to be short and clear for quick evaluation."
)
SAMPLE_MAX_CHARS = 500

client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

TTS_MODEL = os.environ.get("OPENAI_AUDIO_MODEL", "gpt-4o-mini-tts")
TOKENS_PER_CHUNK = 2000
CHARS_PER_TOKEN = 4
MAX_CHARS_PER_CHUNK = TOKENS_PER_CHUNK * CHARS_PER_TOKEN

NARRATOR_INSTRUCTIONS = {
    "The Reluctant Confessor": (
        "Speak softly and intimately, as if confessing something difficult. "
        "Sound hesitant and self-examining, with gentle pauses and a restrained, honest tone."
    ),
    "The Naive Observer": (
        "Speak with innocent curiosity and understated wonder. "
        "Sound inexperienced and nonjudgmental, noticing details without fully grasping their meaning."
    ),
    "The Ancient Sentinel": (
        "Speak in a formal, measured, and resonant tone. "
        "Sound ancient and dutiful, like a timeless guardian issuing calm, authoritative statements."
    ),
    "The Heavy-Hearted Veteran": (
        "Speak with a weary, reflective gravity. "
        "Sound experienced and burdened by memory, compassionate but restrained."
    ),
}


def _resolve_narrator_instructions(narrator: str | None) -> str | None:
    if not narrator:
        return None
    return NARRATOR_INSTRUCTIONS.get(narrator)


def _validate_narrator(narrator: str | None) -> None:
    if narrator and narrator not in NARRATOR_INSTRUCTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported narrator: {narrator}")


async def _read_streamed_audio(response) -> bytes:
    audio_chunks: list[bytes] = []
    async for chunk in response.iter_bytes():
        if chunk:
            audio_chunks.append(chunk)
    if not audio_chunks:
        raise HTTPException(status_code=502, detail="Audio generation failed: empty audio stream")
    return b"".join(audio_chunks)


async def generate_speech_bytes(input_text: str, voice: str, narrator: str | None = None) -> bytes:
    instructions = _resolve_narrator_instructions(narrator)
    async with client.audio.speech.with_streaming_response.create(
        model=TTS_MODEL,
        voice=voice,
        input=input_text,
        response_format="mp3",
        instructions=instructions,
    ) as response:
        return await _read_streamed_audio(response)


def _to_bookly_text(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped in {"#", "##"} or stripped.startswith("# ") or stripped.startswith("## "):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def _split_text_by_chars(text: str, max_chars: int) -> list[str]:
    if not text:
        return []

    chunks: list[str] = []
    current_lines: list[str] = []
    current_len = 0

    for line in text.splitlines():
        line_with_newline = f"{line}\n"

        if len(line_with_newline) > max_chars:
            if current_lines:
                chunks.append("".join(current_lines).rstrip())
                current_lines = []
                current_len = 0
            start = 0
            while start < len(line_with_newline):
                part = line_with_newline[start : start + max_chars]
                chunks.append(part.rstrip())
                start += max_chars
            continue

        if current_lines and current_len + len(line_with_newline) > max_chars:
            chunks.append("".join(current_lines).rstrip())
            current_lines = [line_with_newline]
            current_len = len(line_with_newline)
        else:
            current_lines.append(line_with_newline)
            current_len += len(line_with_newline)

    if current_lines:
        chunks.append("".join(current_lines).rstrip())

    return [chunk for chunk in chunks if chunk.strip()]


app = FastAPI(title="Markdown to Audio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/voices")
def voices() -> dict:
    return {"voices": SUPPORTED_VOICES}


@app.get("/api/narrators")
def narrators() -> dict:
    return {"narrators": list(NARRATOR_INSTRUCTIONS.keys())}


@app.post("/api/convert")
async def convert_markdown_to_audio(
    markdown_file: UploadFile = File(...),
    voice: str = Form("alloy"),
    narrator: str | None = Form(None),
) -> dict:
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")

    if voice not in SUPPORTED_VOICES:
        raise HTTPException(status_code=400, detail=f"Unsupported voice: {voice}")
    _validate_narrator(narrator)

    if not markdown_file.filename or not markdown_file.filename.lower().endswith(".md"):
        raise HTTPException(status_code=400, detail="Please upload a .md file")

    raw_content = await markdown_file.read()
    if not raw_content:
        raise HTTPException(status_code=400, detail="Uploaded markdown file is empty")

    try:
        input_text = raw_content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="Markdown file must be UTF-8 encoded",
        ) from exc

    base_name = Path(markdown_file.filename).stem
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    output_filename = f"{base_name}-{voice}-{timestamp}.mp3"
    output_path = AUDIO_DIR / output_filename

    try:
        audio_bytes = await generate_speech_bytes(
            input_text=input_text,
            voice=voice,
            narrator=narrator,
        )
        output_path.write_bytes(audio_bytes)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Audio generation failed: {exc}") from exc

    return {
        "filename": output_filename,
        "audio_url": f"/audio/{output_filename}",
    }


@app.post("/api/voice-sample")
async def voice_sample(
    voice: str = Form("alloy"),
    narrator: str | None = Form(None),
    sample_text: str | None = Form(None),
) -> dict:
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")

    if voice not in SUPPORTED_VOICES:
        raise HTTPException(status_code=400, detail=f"Unsupported voice: {voice}")
    _validate_narrator(narrator)

    text = (sample_text or SAMPLE_DEFAULT_TEXT).strip()
    if not text:
        raise HTTPException(status_code=400, detail="Sample text cannot be empty")
    if len(text) > SAMPLE_MAX_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Sample text must be at most {SAMPLE_MAX_CHARS} characters",
        )

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    output_filename = f"sample-{voice}-{timestamp}.mp3"
    output_path = AUDIO_DIR / output_filename

    try:
        audio_bytes = await generate_speech_bytes(
            input_text=text,
            voice=voice,
            narrator=narrator,
        )
        output_path.write_bytes(audio_bytes)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Audio generation failed: {exc}") from exc

    return {
        "filename": output_filename,
        "audio_url": f"/audio/{output_filename}",
    }
