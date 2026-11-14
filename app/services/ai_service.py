import os
import json
import asyncio
import logging
import httpx
from enum import Enum
from typing import List, Dict

logger = logging.getLogger("onboarding.ai")


class AiProvider(str, Enum):
    GEMINI  = "gemini"
    OPENAI  = "openai"
    CLAUDE  = "claude"
    GROQ    = "groq"


# ── Configuración — cambia ACTIVE_PROVIDER en .env ────────────
ACTIVE_PROVIDER = AiProvider(os.getenv("AI_PROVIDER", "gemini"))

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
CLAUDE_API_KEY  = os.getenv("CLAUDE_API_KEY", "")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "").strip()
# Groq retira modelos con frecuencia: cámbialo en .env sin tocar código
GROQ_MODEL      = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


async def _llamar_proveedor(
    proveedor: AiProvider,
    system_prompt: str,
    messages: List[Dict[str, str]],
    json_mode: bool,
) -> str:
    if proveedor == AiProvider.GEMINI:
        return await _llamar_gemini(system_prompt, messages, json_mode)
    elif proveedor == AiProvider.OPENAI:
        return await _llamar_openai(system_prompt, messages, json_mode)
    elif proveedor == AiProvider.CLAUDE:
        return await _llamar_claude(system_prompt, messages)
    elif proveedor == AiProvider.GROQ:
        return await _llamar_groq(system_prompt, messages, json_mode)
    raise ValueError(f"Proveedor no soportado: {proveedor}")


async def llamar_ia(
    system_prompt: str,
    messages: List[Dict[str, str]],
    json_mode: bool = False,
) -> str:
    """
    Llama al proveedor de IA activo y retorna el texto de la respuesta.
    messages: lista de {"role": "user"|"assistant", "content": "..."}

    Si el proveedor activo falla (saturación, cuota, timeout) reintenta una
    vez y, si sigue fallando, usa Groq como respaldo cuando hay clave.
    """
    ultimo_error: Exception | None = None
    for intento in range(2):
        try:
            return await _llamar_proveedor(ACTIVE_PROVIDER, system_prompt, messages, json_mode)
        except Exception as e:
            ultimo_error = e
            logger.warning("IA %s falló (intento %d): %s", ACTIVE_PROVIDER.value, intento + 1, e)
            await asyncio.sleep(1)

    if ACTIVE_PROVIDER != AiProvider.GROQ and GROQ_API_KEY:
        try:
            return await _llamar_proveedor(AiProvider.GROQ, system_prompt, messages, json_mode)
        except Exception as e:
            logger.warning("Respaldo Groq también falló: %s", e)
            ultimo_error = e
    raise ultimo_error


# ── Gemini ────────────────────────────────────────────────────
async def _llamar_gemini(system_prompt: str, messages: List[Dict], json_mode: bool = False) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
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
            # Gemini 3.x gasta tokens "pensando": con 2048 el JSON se cortaba
            "maxOutputTokens": 8192,
        },
    }
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"

    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            url, json=payload, headers={"x-goog-api-key": GEMINI_API_KEY}
        )
        if res.status_code != 200:
            raise Exception(f"Gemini respondió con estado {res.status_code}")
        data = res.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


# ── OpenAI ────────────────────────────────────────────────────
async def _llamar_openai(system_prompt: str, messages: List[Dict], json_mode: bool = False) -> str:
    msgs = [{"role": "system", "content": system_prompt}] + messages
    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={"model": "gpt-4o-mini", "messages": msgs, "max_tokens": 4096,
                  **({"response_format": {"type": "json_object"}} if json_mode else {})},
        )
        if res.status_code != 200:
            raise Exception(f"OpenAI respondió con estado {res.status_code}")
        return res.json()["choices"][0]["message"]["content"]


# ── Claude ────────────────────────────────────────────────────
async def _llamar_claude(system_prompt: str, messages: List[Dict]) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
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
            raise Exception(f"Claude respondió con estado {res.status_code}")
        return res.json()["content"][0]["text"]


# ── Groq ──────────────────────────────────────────────────────
async def _llamar_groq(system_prompt: str, messages: List[Dict], json_mode: bool = False) -> str:
    msgs = [{"role": "system", "content": system_prompt}] + messages
    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": GROQ_MODEL,
                "messages": msgs,
                "max_tokens": 4096,
                **({"response_format": {"type": "json_object"}} if json_mode else {}),
            },
        )
        if res.status_code != 200:
            raise Exception(f"Groq respondió con estado {res.status_code}")
        return res.json()["choices"][0]["message"]["content"]