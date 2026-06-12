"""
broker_mt5.py — MT5 direct backend (Windows เท่านั้น)
คุยกับ MetaTrader5 terminal ที่เปิดอยู่บนเครื่องผ่าน MetaTrader5 python lib
interface เดียวกับ broker.BrokerClient — สลับ backend ได้ผ่าน BROKER_BACKEND
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd

from config import (
    MT5_LOGIN,
    MT5_PASSWORD,
    MT5_SERVER,
    MT5_TERMINAL_PATH,
    SYMBOL,
)

logger = logging.getLogger(__name__)

ACCOUNT_CACHE_TTL = 10  # วินาที


class MT5Client:
    """MetaTrader5 direct client — lib เป็น sync ทั้งหมด เลย wrap ด้วย to_thread"""

    def __init__(self) -> None:
        self.connected = False
        self._connect_lock = asyncio.Lock()
        self._cached_info: dict = {}
        self._cached_at: float = 0.0
        self._mt5 = None  # module MetaTrader5 (import ตอน connect)

    @property
    def configured(self) -> bool:
        # MT5 direct ไม่บังคับ credentials — attach terminal ที่ login ค้างไว้ได้
        return True

    # ──────────────────────────────────────────────
    # Connection
    # ──────────────────────────────────────────────

    def _connect_sync(self) -> bool:
        import MetaTrader5 as mt5  # Windows เท่านั้น

        self._mt5 = mt5

        kwargs: dict = {}
        if MT5_TERMINAL_PATH:
            kwargs["path"] = MT5_TERMINAL_PATH
        if MT5_LOGIN:
            kwargs["login"] = int(MT5_LOGIN)
            kwargs["password"] = MT5_PASSWORD
            kwargs["server"] = MT5_SERVER

        if not mt5.initialize(**kwargs):
            logger.error(f"mt5.initialize ล้มเหลว: {mt5.last_error()}")
            return False

        # เปิด symbol ใน Market Watch ไม่งั้นดึงราคาไม่ได้
        if not mt5.symbol_select(SYMBOL, True):
            logger.error(f"ไม่พบ symbol {SYMBOL} — เช็คชื่อ symbol ของ broker (เช่น XAUUSDm)")
            return False

        info = mt5.account_info()
        if info is None:
            logger.error("mt5.account_info ว่าง — terminal ยังไม่ login?")
            return False

        logger.info(f"✅ เชื่อม MT5 สำเร็จ: {info.server} login={info.login}")
        return True

    async def connect(self) -> bool:
        async with self._connect_lock:
            if self.connected:
                return True
            try:
                ok = await asyncio.to_thread(self._connect_sync)
                self.connected = ok
                return ok
            except ImportError:
                logger.error("ไม่มี MetaTrader5 lib — รันได้แค่ Windows (pip install MetaTrader5)")
                return False
            except Exception as e:
                logger.error(f"MT5 connect error: {e}")
                return False

    async def _ensure(self) -> bool:
        if self.connected:
            return True
        return await self.connect()

    # ──────────────────────────────────────────────
    # Market data
    # ──────────────────────────────────────────────

    def _get_candles_sync(self, tf: str, bars: int) -> pd.DataFrame:
        mt5 = self._mt5
        tf_map = {
            "1h": mt5.TIMEFRAME_H1, "H1": mt5.TIMEFRAME_H1,
            "15min": mt5.TIMEFRAME_M15, "15m": mt5.TIMEFRAME_M15, "M15": mt5.TIMEFRAME_M15,
            "5min": mt5.TIMEFRAME_M5, "5m": mt5.TIMEFRAME_M5, "M5": mt5.TIMEFRAME_M5,
        }
        rates = mt5.copy_rates_from_pos(SYMBOL, tf_map[tf], 0, bars)
        if rates is None or len(rates) == 0:
            logger.warning(f"copy_rates ว่าง [{tf}]: {mt5.last_error()}")
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.rename(columns={"tick_volume": "volume"}, inplace=True)
        df = df[["time", "open", "high", "low", "close", "volume"]]
        df.sort_values("time", inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    async def get_candles(self, tf: str, bars: int) -> pd.DataFrame:
        if not await self._ensure():
            return pd.DataFrame()
        return await asyncio.to_thread(self._get_candles_sync, tf, bars)

    # ──────────────────────────────────────────────
    # Account
    # ──────────────────────────────────────────────

    def _account_info_sync(self) -> dict:
        info = self._mt5.account_info()
        if info is None:
            raise RuntimeError(f"account_info ว่าง: {self._mt5.last_error()}")
        return {
            "balance":  float(info.balance),
            "equity":   float(info.equity),
            "floating": float(info.profit),
            "currency": info.currency,
            "broker":   info.company,
            "server":   info.server,
        }

    async def get_account_info(self) -> dict:
        now = time.time()
        if self._cached_info and now - self._cached_at < ACCOUNT_CACHE_TTL:
            return self._cached_info

        if not await self._ensure():
            return self._cached_info

        try:
            self._cached_info = await asyncio.to_thread(self._account_info_sync)
            self._cached_at = now
        except Exception as e:
            logger.error(f"mt5 get_account_info error: {e}")
            self.connected = False
        return self._cached_info

    # ──────────────────────────────────────────────
    # Positions / orders
    # ──────────────────────────────────────────────

    def _positions_sync(self) -> list:
        mt5 = self._mt5
        positions = mt5.positions_get(symbol=SYMBOL) or []
        # normalize เป็น dict ให้หน้าตาเหมือน MetaApi (id เป็น str)
        return [
            {
                "id":        str(p.ticket),
                "symbol":    p.symbol,
                "type":      "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume":    float(p.volume),
                "openPrice": float(p.price_open),
                "sl":        float(p.sl),
                "tp":        float(p.tp),
                "profit":    float(p.profit),
            }
            for p in positions
        ]

    async def get_open_positions(self) -> list:
        if not await self._ensure():
            return []
        try:
            return await asyncio.to_thread(self._positions_sync)
        except Exception as e:
            logger.error(f"mt5 get_open_positions error: {e}")
            self.connected = False
            return []

    def _place_order_sync(self, direction: str, lot: float, sl: float, tp: float) -> Optional[dict]:
        mt5 = self._mt5
        tick = mt5.symbol_info_tick(SYMBOL)
        if tick is None:
            logger.error(f"ไม่มี tick ของ {SYMBOL}")
            return None

        is_buy = direction == "BUY"
        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       SYMBOL,
            "volume":       lot,
            "type":         mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
            "price":        tick.ask if is_buy else tick.bid,
            "sl":           float(sl),
            "tp":           float(tp),
            "deviation":    20,
            "magic":        234000,
            "comment":      "SMC-AI-Bot",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            code = getattr(result, "retcode", "none")
            comment = getattr(result, "comment", mt5.last_error())
            logger.error(f"order_send ล้มเหลว retcode={code}: {comment}")
            return None

        return {"orderId": str(result.order), "price": float(result.price)}

    async def place_market_order(self, direction: str, lot: float, sl: float, tp: float) -> Optional[dict]:
        if not await self._ensure():
            return None
        return await asyncio.to_thread(self._place_order_sync, direction, lot, sl, tp)

    def _close_position_sync(self, position_id: str) -> bool:
        mt5 = self._mt5
        positions = mt5.positions_get(ticket=int(position_id))
        if not positions:
            logger.warning(f"ไม่พบ position {position_id}")
            return False
        p = positions[0]

        tick = mt5.symbol_info_tick(p.symbol)
        is_buy = p.type == mt5.ORDER_TYPE_BUY
        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       p.symbol,
            "volume":       float(p.volume),
            # ปิด = ส่ง order ฝั่งตรงข้าม ระบุ position ticket
            "type":         mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
            "position":     p.ticket,
            "price":        tick.bid if is_buy else tick.ask,
            "deviation":    20,
            "magic":        234000,
            "comment":      "SMC-AI-Bot close",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
        if not ok:
            logger.error(f"close_position ล้มเหลว: {getattr(result, 'comment', mt5.last_error())}")
        return ok

    async def close_position(self, position_id: str) -> bool:
        if not await self._ensure():
            return False
        return await asyncio.to_thread(self._close_position_sync, position_id)

    def _deals_sync(self, position_id: str) -> list:
        mt5 = self._mt5
        date_from = datetime(2020, 1, 1)
        date_to = datetime.now(timezone.utc) + timedelta(days=1)
        deals = mt5.history_deals_get(date_from, date_to, position=int(position_id)) or []
        return [
            {"profit": float(d.profit) + float(d.swap) + float(d.commission), "price": float(d.price)}
            for d in deals
        ]

    async def get_deals_by_position(self, position_id: str) -> list:
        if not await self._ensure():
            return []
        try:
            return await asyncio.to_thread(self._deals_sync, position_id)
        except Exception as e:
            logger.warning(f"mt5 get_deals error ({position_id}): {e}")
            return []
