"""
ai.py — AI provider abstraction
รองรับ Claude (anthropic API) และ local model ผ่าน Ollama
สลับด้วย AI_PROVIDER ใน .env โดยไม่ต้องแก้โค้ดที่เรียกใช้
"""
import json
import logging
import urllib.request

from config import AI_PROVIDER, AI_MODEL, OLLAMA_HOST, ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)


def analyze(prompt: str, max_tokens: int = 1000) -> str:
    """ส่ง prompt ไปยัง provider ที่ตั้งค่าไว้ return ข้อความวิเคราะห์ (blocking)"""
    if AI_PROVIDER == "ollama":
        return _ollama(prompt, max_tokens)
    return _anthropic(prompt, max_tokens)


def _anthropic(prompt: str, max_tokens: int) -> str:
    if not ANTHROPIC_API_KEY:
        return "ไม่มี ANTHROPIC_API_KEY"
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=AI_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def _ollama(prompt: str, max_tokens: int) -> str:
    """เรียก local Ollama ผ่าน HTTP (urllib stdlib — ไม่ต้องลง dependency เพิ่ม)"""
    payload = json.dumps({
        "model":   AI_MODEL,
        "prompt":  prompt,
        "stream":  False,
        "options": {"num_predict": max_tokens},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
        return data.get("response", "").strip()
    except Exception as e:
        logger.error(f"ollama error: {e}")
        return f"local model วิเคราะห์ไม่ได้: {e}"
