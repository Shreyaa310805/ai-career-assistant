"""Small async HTTP client helpers for Groq speech and image inference."""
import base64
import json

import httpx


GROQ_API_BASE = "https://api.groq.com/openai/v1"
MIME_SUFFIXES = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/wav": ".wav",
}


async def transcribe(data: bytes, mime: str, api_key: str, model: str) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{GROQ_API_BASE}/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            data={"model": model, "response_format": "json", "temperature": "0"},
            files={"file": (f"recording{MIME_SUFFIXES[mime]}", data, mime)},
        )
        response.raise_for_status()
        return str(response.json().get("text", "")).strip()


async def analyze_image(data: bytes, prompt: str, api_key: str, model: str) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
            ],
        }],
        "temperature": 0,
        "max_completion_tokens": 512,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=35) as client:
        response = await client.post(
            f"{GROQ_API_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
