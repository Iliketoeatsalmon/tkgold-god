"""
server.py — FastAPI backend สำหรับ Dashboard
รันได้ standalone แม้ bot ไม่ทำงาน (ดึงจาก DB)
"""
import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import ai
import db
from broker import broker
from config import ANTHROPIC_API_KEY, AI_PROVIDER, WS_PUSH_INTERVAL, SYMBOL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Shared state (อ่านจาก bot ถ้ารัน in-process)
# ──────────────────────────────────────────────
_bot_instance = None  # inject ถ้ารัน bot + server ใน process เดียว
_ws_clients: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """เตรียม DB + เชื่อม broker เมื่อ startup"""
    db.init_db()
    logger.info("Server เริ่มทำงาน DB ready")

    # เชื่อม MetaApi แบบ background — ไม่ block server start
    if broker.configured:
        asyncio.create_task(broker.connect())
    else:
        logger.warning("METAAPI_TOKEN/ACCOUNT_ID ไม่ครบ — dashboard จะไม่เห็น account จริง")

    yield
    logger.info("Server shutdown")


app = FastAPI(
    title="XAUUSD SMC AI Trading API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # "*" + credentials=True ผิด spec, browser ปฏิเสธ
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────

class AIAnalysisRequest(BaseModel):
    signal_id: int


# ──────────────────────────────────────────────
# Status & account
# ──────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    """สถานะ bot, account info, signal ปัจจุบัน"""
    bot_running = _bot_instance is not None and getattr(_bot_instance, "running", False)

    account_info: dict = {}
    current_signal: dict = {}

    if _bot_instance:
        account_info = getattr(_bot_instance, "account_info", {})
        current_signal = getattr(_bot_instance, "current_signal", {})

    # ไม่มี bot in-process → ดึง account จริงผ่าน broker connection ของ server
    if not account_info and broker.configured:
        account_info = await broker.get_account_info()

    # ดึง signal ล่าสุดจาก DB ถ้า bot ไม่รัน
    if not current_signal:
        signals = db.get_signals(limit=1)
        current_signal = signals[0] if signals else {}

    return {
        "bot_running":      bot_running,
        "broker_connected": broker.connected or bool(_bot_instance),
        "account":          account_info,
        "current_signal":   current_signal,
        "timestamp":        datetime.now(timezone.utc).isoformat(),
    }


# ──────────────────────────────────────────────
# Signals
# ──────────────────────────────────────────────

@app.get("/api/signals")
async def get_signals(limit: int = 50):
    """ดึง signal history"""
    return db.get_signals(limit=limit)


@app.get("/api/signals/live")
async def get_live_signal():
    """Signal ล่าสุด"""
    signals = db.get_signals(limit=1)
    if not signals:
        return {"message": "ยังไม่มี signal"}
    return signals[0]


# ──────────────────────────────────────────────
# Orders
# ──────────────────────────────────────────────

@app.get("/api/orders")
async def get_orders(limit: int = 50, status: str = "all"):
    """ดึง order history กรองตาม status: all | open | closed"""
    if status not in ("all", "open", "closed"):
        raise HTTPException(400, "status ต้องเป็น all, open หรือ closed")
    return db.get_orders(limit=limit, status=status)


@app.get("/api/orders/stats")
async def get_order_stats():
    """win rate, PnL รวม, best/worst trade"""
    return db.get_order_stats()


@app.get("/api/positions")
async def get_positions():
    """Positions ที่เปิดอยู่จริงจาก broker"""
    if not broker.configured:
        return []
    return await broker.get_open_positions()


# ──────────────────────────────────────────────
# Analytics
# ──────────────────────────────────────────────

@app.get("/api/equity-curve")
async def get_equity_curve(limit: int = 100):
    """Equity curve จาก closed orders"""
    return db.get_equity_curve(limit=limit)


@app.get("/api/ai-progress")
async def get_ai_progress(limit: int = 50):
    """AI progress history"""
    return db.get_ai_progress(limit=limit)


@app.get("/api/daily-stats")
async def get_daily_stats(limit: int = 30):
    """สถิติรายวัน"""
    return db.get_daily_stats_history(limit=limit)


# ──────────────────────────────────────────────
# AI Analysis
# ──────────────────────────────────────────────

@app.post("/api/ai-analysis")
async def ai_analysis(body: AIAnalysisRequest):
    """วิเคราะห์ signal ผ่าน AI provider ที่ตั้งค่าไว้ (Claude หรือ local model)"""
    if AI_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
        raise HTTPException(400, "ไม่มี ANTHROPIC_API_KEY")

    signal = db.get_signal_by_id(body.signal_id)
    if not signal:
        raise HTTPException(404, f"ไม่พบ signal id={body.signal_id}")

    try:
        prompt = f"""วิเคราะห์ signal XAUUSD นี้เป็นภาษาไทยอย่างละเอียด:

Direction: {signal.get('direction')}
Confidence: {signal.get('confidence')}%
Entry: {signal.get('entry')}
SL: {signal.get('sl')}
TP: {signal.get('tp')}
R:R: {signal.get('rr')}
Fib Level: {signal.get('fib_hit')}
FVG: {'ใช่' if signal.get('fvg') else 'ไม่'}
CHoCH: {'ใช่' if signal.get('choch') else 'ไม่'}
BOS: {'ใช่' if signal.get('bos') else 'ไม่'}

เหตุผลจากระบบ:
{signal.get('reason')}

กรุณาวิเคราะห์:
1. ความน่าเชื่อถือของ setup
2. ความเสี่ยงและจุดอ่อน
3. แนะนำการ manage trade"""

        # ai.analyze เป็น blocking I/O — รันใน thread แยกไม่ให้ block event loop
        analysis = await asyncio.to_thread(ai.analyze, prompt, 1000)
        return {
            "signal_id": body.signal_id,
            "analysis":  analysis,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"ai_analysis error: {e}")
        raise HTTPException(500, str(e))


# ──────────────────────────────────────────────
# WebSocket — live updates
# ──────────────────────────────────────────────

@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    """Push signal และ price update ทุก WS_PUSH_INTERVAL วินาที"""
    await ws.accept()
    _ws_clients.append(ws)
    logger.info(f"WebSocket client เชื่อมต่อ (total={len(_ws_clients)})")

    try:
        while True:
            # ดึง signal ล่าสุด
            signals = db.get_signals(limit=1)
            latest = signals[0] if signals else {}

            # account info จาก bot ก่อน, ไม่มีก็ใช้ broker ของ server
            account = {}
            if _bot_instance:
                account = getattr(_bot_instance, "account_info", {})
            if not account and broker.configured:
                account = await broker.get_account_info()

            payload = {
                "type":      "update",
                "signal":    latest,
                "account":   account,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            await ws.send_text(json.dumps(payload, default=str))
            await asyncio.sleep(WS_PUSH_INTERVAL)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnect")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


# ──────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
