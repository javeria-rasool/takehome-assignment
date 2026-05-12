"""
AI Client — Gemini REST API via requests only. No litellm needed.
Works on Python 3.8+. Supports tool-use loops and vision (base64 images).
"""
import json
import time
from typing import Callable, Dict, List, Optional

import requests

from .config import Config
from .logger import get_logger

logger = get_logger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-2.5-flash"   # fast, free, supports tool use + vision
VISION_MODEL = "gemini-2.5-flash"   # same model handles vision too


# ---------------------------------------------------------------------------
# Schema conversion  (JSON Schema lowercase → Gemini uppercase)
# ---------------------------------------------------------------------------

_TYPE_MAP = {
    "object": "OBJECT", "string": "STRING", "integer": "INTEGER",
    "number": "NUMBER", "boolean": "BOOLEAN", "array": "ARRAY",
}


def _to_gemini_schema(schema: dict) -> dict:
    result: dict = {}
    if "type" in schema:
        result["type"] = _TYPE_MAP.get(schema["type"].lower(), schema["type"].upper())
    if "description" in schema:
        result["description"] = schema["description"]
    if "properties" in schema:
        result["properties"] = {k: _to_gemini_schema(v) for k, v in schema["properties"].items()}
    if "required" in schema:
        result["required"] = schema["required"]
    if "items" in schema:
        result["items"] = _to_gemini_schema(schema["items"])
    return result


def _to_gemini_tools(tools: List[dict]) -> List[dict]:
    declarations = []
    for t in tools:
        schema = t.get("parameters") or t.get("input_schema", {})
        declarations.append({
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": _to_gemini_schema(schema),
        })
    return [{"functionDeclarations": declarations}]


# ---------------------------------------------------------------------------
# HTTP call with rate-limit retry
# ---------------------------------------------------------------------------

def _call(model: str, payload: dict, max_attempts: int = 6) -> dict:
    url = f"{GEMINI_BASE}/models/{model}:generateContent?key={Config.GEMINI_API_KEY}"
    for attempt in range(1, max_attempts + 1):
        resp = requests.post(url, json=payload, timeout=120)
        if resp.status_code == 429 or resp.status_code == 503:
            wait = 2 ** attempt
            logger.warning(f"Rate limit / overload (attempt {attempt}), retrying in {wait}s…")
            time.sleep(wait)
            continue
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API {resp.status_code}: {resp.text[:600]}")
        return resp.json()
    raise RuntimeError("Gemini API: exceeded retry attempts (rate limit)")


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------

def _image_url_to_part(item: dict) -> Optional[dict]:
    """Convert an image_url content block to a Gemini inlineData part."""
    url_data = item.get("image_url", {}).get("url", "")
    if url_data.startswith("data:"):
        # data:<mediaType>;base64,<data>
        header, b64 = url_data.split(";base64,", 1)
        media_type = header.replace("data:", "")
        return {"inlineData": {"mimeType": media_type, "data": b64}}
    return None


# ---------------------------------------------------------------------------
# Agentic tool-use loop
# ---------------------------------------------------------------------------

def tool_loop(
    system: str,
    user_message: str,
    tools: List[dict],
    dispatch: Callable[[str, dict], str],
    max_iterations: int = 30,
    vision: bool = False,
    extra_user_content: Optional[List[dict]] = None,
) -> str:
    model = VISION_MODEL if vision else DEFAULT_MODEL
    gemini_tools = _to_gemini_tools(tools) if tools else []

    # Build first user turn
    first_parts: List[dict] = [{"text": user_message}]
    for item in (extra_user_content or []):
        if item.get("type") == "image_url":
            part = _image_url_to_part(item)
            if part:
                first_parts.append(part)
        elif item.get("type") == "text":
            first_parts.append({"text": item["text"]})

    history: List[dict] = [{"role": "user", "parts": first_parts}]
    last_text = ""

    for iteration in range(max_iterations):
        logger.debug(f"AI loop iteration {iteration + 1}/{max_iterations}")

        payload: dict = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": history,
            "generationConfig": {"maxOutputTokens": 8192},
        }
        if gemini_tools:
            payload["tools"] = gemini_tools

        data = _call(model, payload)
        candidate = data.get("candidates", [{}])[0]
        parts = candidate.get("content", {}).get("parts", [])
        finish = candidate.get("finishReason", "STOP")

        text_parts = [p["text"] for p in parts if "text" in p]
        func_calls = [p["functionCall"] for p in parts if "functionCall" in p]

        if text_parts:
            last_text = "\n".join(text_parts)
            logger.debug(f"AI text: {last_text[:120]}")

        # Add model turn to history
        history.append({"role": "model", "parts": parts})

        if not func_calls or finish == "STOP":
            logger.debug("AI loop: end")
            break

        # Execute tools and feed results back
        response_parts: List[dict] = []
        for fc in func_calls:
            name = fc["name"]
            args = fc.get("args", {})
            logger.info(f"Tool: {name}({list(args.keys())})")
            result = dispatch(name, args)
            response_parts.append({
                "functionResponse": {
                    "name": name,
                    "response": {"result": str(result)},
                }
            })
        history.append({"role": "user", "parts": response_parts})

    return last_text


# ---------------------------------------------------------------------------
# Single-shot completion (with optional vision)
# ---------------------------------------------------------------------------

def simple_completion(
    prompt: str,
    vision_content: Optional[List[dict]] = None,
) -> str:
    model = VISION_MODEL if vision_content else DEFAULT_MODEL
    parts: List[dict] = [{"text": prompt}]

    for item in (vision_content or []):
        if item.get("type") == "image_url":
            part = _image_url_to_part(item)
            if part:
                parts.append(part)
        elif item.get("type") == "text":
            parts.append({"text": item["text"]})

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"maxOutputTokens": 4096},
    }
    data = _call(model, payload)
    candidate = data.get("candidates", [{}])[0]
    texts = [p.get("text", "") for p in candidate.get("content", {}).get("parts", []) if "text" in p]
    return "\n".join(texts)
