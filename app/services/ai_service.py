import os
import json
import httpx
from enum import Enum
from typing import List, Dict


class AiProvider(str, Enum):
    GEMINI  = "gemini"
    OPENAI  = "openai"
    CLAUDE  = "claude"
    GROQ    = "groq"


# ── Configuración — cambia ACTIVE_PROVIDER en .env ────────────
ACTIVE_PROVIDER = AiProvider(os.getenv("AI_PROVIDER", "gemini"))

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
CLAUDE_API_KEY  = os.getenv("CLAUDE_API_KEY", "")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")


async def llamar_ia(
    system_prompt: str,
    messages: List[Dict[str, str]],
) -> str:
    """
    Llama al proveedor de IA activo y retorna el texto de la respuesta.
    messages: lista de {"role": "user"|"assistant", "content": "..."}
    """
    if ACTIVE_PROVIDER == AiProvider.GEMINI:
        return await _llamar_gemini(system_prompt, messages)
    elif ACTIVE_PROVIDER == AiProvider.OPENAI:
        return await _llamar_openai(system_prompt, messages)
    elif ACTIVE_PROVIDER == AiProvider.CLAUDE:
        return await _llamar_claude(system_prompt, messages)
    elif ACTIVE_PROVIDER == AiProvider.GROQ:
        return await _llamar_groq(system_prompt, messages)
    else:
        raise ValueError(f"Proveedor no soportado: {ACTIVE_PROVIDER}")


# ── Gemini ────────────────────────────────────────────────────
async def _llamar_gemini(system_prompt: str, messages: List[Dict]) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )

    # Gemini usa "contents" con roles "user" y "model"
    contents = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(url, json=payload)
        if res.status_code != 200:
            raise Exception(f"Gemini error {res.status_code}: {res.text}")
        data = res.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


# ── OpenAI ────────────────────────────────────────────────────
async def _llamar_openai(system_prompt: str, messages: List[Dict]) -> str:
    msgs = [{"role": "system", "content": system_prompt}] + messages
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={"model": "gpt-4o-mini", "messages": msgs, "max_tokens": 2048},
        )
        if res.status_code != 200:
            raise Exception(f"OpenAI error {res.status_code}: {res.text}")
        return res.json()["choices"][0]["message"]["content"]


# ── Claude ────────────────────────────────────────────────────
async def _llamar_claude(system_prompt: str, messages: List[Dict]) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-opus-4-5",
                "max_tokens": 2048,
                "system": system_prompt,
                "messages": messages,
            },
        )
        if res.status_code != 200:
            raise Exception(f"Claude error {res.status_code}: {res.text}")
        return res.json()["content"][0]["text"]


# ── Groq ──────────────────────────────────────────────────────
async def _llamar_groq(system_prompt: str, messages: List[Dict]) -> str:
    msgs = [{"role": "system", "content": system_prompt}] + messages
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": msgs,
                "max_tokens": 2048,
            },
        )
        if res.status_code != 200:
            raise Exception(f"Groq error {res.status_code}: {res.text}")
        return res.json()["choices"][0]["message"]["content"]