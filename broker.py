"""
broker.py — broker connection layer ใช้ร่วม bot + server
backend เลือกผ่าน BROKER_BACKEND: "metaapi" (cloud) หรือ "mt5" (Windows direct)
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from config import (
    METAAPI_TOKEN,
    ACCOUNT_ID,
    METAAPI_RETRY_DELAY,
    METAAPI_MAX_RETRIES,
    BROKER_BACKEND,
    SYMBOL,
)

logger = logging.getLogger(__name__)

# cache account info กี่วินาทีก่อน fetch ใหม่ (กัน rate limit free tier)
ACCOUNT_CACHE_TTL = 10


class BrokerClient:
    """MetaApi RPC client สำหรับอ่าน account info / positions"""

    def __init__(self) -> None:
        self.api = None
        self.account = None
        self.connection = None
        self.connected = False
        self._connect_lock = asyncio.Lock()
        self._cached_info: dict = {}
        self._cached_at: float = 0.0

    @property
    def configured(self) -> bool:
        """มี credentials ครบหรือยัง"""
        return bool(METAAPI_TOKEN and ACCOUNT_ID)

    async def connect(self) -> bool:
        """เชื่อม MetaApi — กันเชื่อมซ้ำด้วย lock, return True ถ้าสำเร็จ"""
        if not self.configured:
            logger.warning("ไม่มี METAAPI_TOKEN/ACCOUNT_ID — ข้ามการเชื่อม broker")
            return False

        async with self._connect_lock:
            if self.connected:
                return True

            from metaapi_cloud_sdk import MetaApi  # type: ignore

            for attempt in range(1, METAAPI_MAX_RETRIES + 1):
                try:
                    logger.info(f"Server เชื่อม MetaApi... (ครั้งที่ {attempt})")
                    self.api = MetaApi(METAAPI_TOKEN)
                    self.account = await self.api.metatrader_account_api.get_account(ACCOUNT_ID)

                    if self.account.state not in ("DEPLOYED", "DEPLOYING"):
                        await self.account.deploy()
                    await self.account.wait_connected()

                    self.connection = self.account.get_rpc_connection()
                    await self.connection.connect()
                    await self.connection.wait_synchronized()

                    self.connected = True
                    logger.info("✅ Server เชื่อม MetaApi สำเร็จ")
                    return True

                except Exception as e:
                    logger.error(f"Server เชื่อม MetaApi ล้มเหลว: {e}")
                    # billing/credential error = permanent, retry ไปก็เปลือง
                    msg = str(e).lower()
                    if "top up" in msg or "unauthorized" in msg or "forbidden" in msg:
                        logger.error("Error ถาวร (billing/credentials) — หยุด retry")
                        return False
                    if attempt < METAAPI_MAX_RETRIES:
                        await asyncio.sleep(METAAPI_RETRY_DELAY)

            return False

    async def get_account_info(self) -> dict:
        """ดึง balance/equity/floating — cache ตาม TTL กัน rate limit"""
        now = time.time()
        if self._cached_info and now - self._cached_at < ACCOUNT_CACHE_TTL:
            return self._cached_info

        if not self.connected:
            ok = await self.connect()
            if not ok:
                return self._cached_info

        try:
            info = await self.connection.get_account_information()
            self._cached_info = {
                "balance":  float(info.get("balance", 0)),
                "equity":   float(info.get("equity", 0)),
                "floating": float(info.get("equity", 0)) - float(info.get("balance", 0)),
                "currency": info.get("currency", "USD"),
                "broker":   info.get("broker", ""),
                "server":   info.get("server", ""),
            }
            self._cached_at = now
        except Exception as e:
            logger.error(f"broker get_account_info error: {e}")
            self.connected = False  # ให้ reconnect ครั้งหน้า

        return self._cached_info

    async def get_open_positions(self) -> list:
        """positions ที่เปิดอยู่ — normalize id เป็น str"""
        if not self.connected:
            ok = await self.connect()
            if not ok:
                return []
        try:
            positions = await self.connection.get_positions()
            result = []
            for p in positions:
                d = p if isinstance(p, dict) else vars(p)
                d["id"] = str(d.get("id", ""))
                result.append(d)
            return result
        except Exception as e:
            logger.error(f"broker get_open_positions error: {e}")
            self.connected = False
            return []

    # ──────────────────────────────────────────────
    # Market data / trading (ใช้โดย bot)
    # ──────────────────────────────────────────────

    async def get_candles(self, tf: str, bars: int) -> pd.DataFrame:
        """ดึง candles แปลงเป็น DataFrame"""
        if not await self.connect():
            return pd.DataFrame()

        tf_map = {"1h": "1h", "15min": "15m", "5min": "5m", "H1": "1h", "M15": "15m", "M5": "5m"}
        api_tf = tf_map.get(tf, tf)

        candles = await self.connection.get_historical_candles(
            SYMBOL, api_tf, datetime.now(timezone.utc), bars
        )

        rows = [{
            "time":   c.get("time"),
            "open":   float(c.get("open", 0)),
            "high":   float(c.get("high", 0)),
            "low":    float(c.get("low", 0)),
            "close":  float(c.get("close", 0)),
            "volume": float(c.get("tickVolume", 0)),
        } for c in candles]

        df = pd.DataFrame(rows)
        if not df.empty:
            df["time"] = pd.to_datetime(df["time"])
            df.sort_values("time", inplace=True)
            df.reset_index(drop=True, inplace=True)
        return df

    async def place_market_order(self, direction: str, lot: float, sl: float, tp: float) -> Optional[dict]:
        """ส่ง market order พร้อม SL/TP"""
        if not await self.connect():
            return None
        try:
            opts = {"comment": "SMC-AI-Bot", "clientId": "xaubot"}
            if direction == "BUY":
                result = await self.connection.create_market_buy_order(SYMBOL, lot, sl, tp, opts)
            else:
                result = await self.connection.create_market_sell_order(SYMBOL, lot, sl, tp, opts)
            return {"orderId": str(result.get("orderId", ""))}
        except Exception as e:
            logger.error(f"broker place_market_order error: {e}")
            return None

    async def close_position(self, position_id: str) -> bool:
        if not await self.connect():
            return False
        try:
            await self.connection.close_position(position_id)
            return True
        except Exception as e:
            logger.error(f"broker close_position error: {e}")
            return False

    async def get_deals_by_position(self, position_id: str) -> list:
        """deals ของ position (ใช้คำนวณ pnl ตอนปิด) — best-effort"""
        if not await self.connect():
            return []
        try:
            getter = getattr(self.connection, "get_deals_by_position", None)
            if getter is None:
                return []
            res = await getter(position_id)
            deals = res.get("deals", []) if isinstance(res, dict) else res
            return [
                {"profit": float(d.get("profit", 0)), "price": float(d.get("price", 0))}
                for d in deals
            ]
        except Exception as e:
            logger.warning(f"broker get_deals error ({position_id}): {e}")
            return []


# ──────────────────────────────────────────────
# Factory — singleton ใช้ร่วมทั้ง bot และ server
# ──────────────────────────────────────────────

if BROKER_BACKEND == "mt5":
    from broker_mt5 import MT5Client
    broker = MT5Client()
    logger.info("Broker backend: MT5 direct")
else:
    broker = BrokerClient()
    logger.info("Broker backend: MetaApi cloud")
