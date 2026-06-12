"""
strategy.py — SMC Strategy engine สำหรับ XAUUSD
ตรวจจับ Swing, Fibonacci, FVG, CHoCH, BOS และสร้าง signal
"""
import logging
from typing import Optional
import pandas as pd
import numpy as np
from config import (
    FIB_LEVELS, FIB_ENTRY_ZONE, FIB_TP_LEVELS,
    ATR_SL_MULTIPLIER, MIN_RR_RATIO
)

logger = logging.getLogger(__name__)


class SMCStrategy:
    """กลยุทธ์ Smart Money Concepts ผสม Fibonacci"""

    def detect_swings(
        self, df: pd.DataFrame, lookback: int = 10
    ) -> dict[str, list]:
        """
        หา swing high/low ด้วย ZigZag (lookback แท่งซ้าย/ขวา)
        return: {"highs": [(index, price)], "lows": [(index, price)]}
        """
        highs: list[tuple[int, float]] = []
        lows: list[tuple[int, float]] = []

        for i in range(lookback, len(df) - lookback):
            high = df["high"].iloc[i]
            low = df["low"].iloc[i]

            # swing high — ค่าสูงสุดในกรอบ lookback
            if high == df["high"].iloc[i - lookback: i + lookback + 1].max():
                highs.append((i, high))

            # swing low — ค่าต่ำสุดในกรอบ lookback
            if low == df["low"].iloc[i - lookback: i + lookback + 1].min():
                lows.append((i, low))

        return {"highs": highs, "lows": lows}

    def draw_fib(
        self,
        swing_low: float,
        swing_high: float,
        direction: str,
    ) -> dict[float, float]:
        """
        คำนวณราคาของแต่ละ Fibonacci level
        direction BUY: วัดจาก low ขึ้น high
        direction SELL: วัดจาก high ลง low (inverse)
        return: {level: price}
        """
        diff = swing_high - swing_low
        fib_prices: dict[float, float] = {}

        for level in FIB_LEVELS:
            if direction == "BUY":
                # retracement จาก high กลับมา low
                fib_prices[level] = swing_high - diff * level
            else:
                # retracement จาก low กลับมา high
                fib_prices[level] = swing_low + diff * level

        return fib_prices

    def detect_fvg(self, df: pd.DataFrame) -> list[dict]:
        """
        หา Fair Value Gap (FVG) — gap ระหว่าง candle 1 กับ 3
        Bullish FVG: high[i-2] < low[i]  (gap บน)
        Bearish FVG: low[i-2] > high[i]  (gap ล่าง)
        return: list of {"type": "bull"|"bear", "top": price, "bottom": price, "index": i}
        """
        fvg_list: list[dict] = []

        for i in range(2, len(df)):
            high_prev = df["high"].iloc[i - 2]
            low_prev = df["low"].iloc[i - 2]
            high_curr = df["high"].iloc[i]
            low_curr = df["low"].iloc[i]

            # Bullish FVG — gap เหนือ candle 1 ถึงใต้ candle 3
            if high_prev < low_curr:
                fvg_list.append({
                    "type":   "bull",
                    "top":    low_curr,
                    "bottom": high_prev,
                    "index":  i,
                })

            # Bearish FVG — gap ใต้ candle 1 ถึงเหนือ candle 3
            elif low_prev > high_curr:
                fvg_list.append({
                    "type":   "bear",
                    "top":    low_prev,
                    "bottom": high_curr,
                    "index":  i,
                })

        return fvg_list

    def detect_choch(
        self, df: pd.DataFrame, swings: dict
    ) -> tuple[bool, str]:
        """
        Change of Character — เส้นแนวโน้มเปลี่ยน
        BUY CHoCH: swing low ใหม่สูงกว่า swing low ก่อนหน้า (bullish flip)
        SELL CHoCH: swing high ใหม่ต่ำกว่า swing high ก่อนหน้า (bearish flip)
        return: (detected: bool, direction: "BUY"|"SELL"|"")
        """
        lows = swings.get("lows", [])
        highs = swings.get("highs", [])

        # ต้องมี swing อย่างน้อย 2 จุด
        if len(lows) >= 2:
            if lows[-1][1] > lows[-2][1]:  # low ล่าสุดสูงกว่า low ก่อน = bullish
                return True, "BUY"

        if len(highs) >= 2:
            if highs[-1][1] < highs[-2][1]:  # high ล่าสุดต่ำกว่า high ก่อน = bearish
                return True, "SELL"

        return False, ""

    def detect_bos(
        self, df: pd.DataFrame, swings: dict
    ) -> tuple[bool, str]:
        """
        Break of Structure — ราคาทะลุ swing point ก่อนหน้า
        BUY BOS: close > swing high ก่อนหน้า
        SELL BOS: close < swing low ก่อนหน้า
        return: (detected: bool, direction: "BUY"|"SELL"|"")
        """
        if df.empty:
            return False, ""

        last_close = df["close"].iloc[-1]
        highs = swings.get("highs", [])
        lows = swings.get("lows", [])

        if highs and last_close > highs[-1][1]:
            return True, "BUY"

        if lows and last_close < lows[-1][1]:
            return True, "SELL"

        return False, ""

    def check_fib_fvg_confluence(
        self,
        price: float,
        fib_prices: dict[float, float],
        fvg_list: list[dict],
        direction: str,
    ) -> tuple[bool, Optional[float]]:
        """
        ราคาอยู่ใน golden zone (0.618-0.786) และมี FVG ซ้อนทับในโซนเดียวกัน
        return: (confluence: bool, fib_level_hit: float | None)
        """
        zone_low = fib_prices.get(FIB_ENTRY_ZONE[0])
        zone_high = fib_prices.get(FIB_ENTRY_ZONE[1])

        if zone_low is None or zone_high is None:
            return False, None

        # ปรับลำดับตาม direction (BUY: zone_high > zone_low)
        lo = min(zone_low, zone_high)
        hi = max(zone_low, zone_high)

        # ราคาอยู่ใน Fib entry zone?
        if not (lo <= price <= hi):
            return False, None

        # หา level ที่ใกล้ที่สุด
        hit_level = min(
            FIB_ENTRY_ZONE,
            key=lambda lv: abs(fib_prices.get(lv, 9999) - price)
        )

        # ตรวจว่ามี FVG ซ้อนในโซน
        fvg_match_type = "bull" if direction == "BUY" else "bear"
        for fvg in fvg_list:
            if fvg["type"] != fvg_match_type:
                continue
            # FVG ซ้อนทับกับ Fib zone
            if fvg["bottom"] <= hi and fvg["top"] >= lo:
                return True, hit_level

        return False, None

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """ATR (Average True Range) สำหรับคำนวณ SL"""
        high = df["high"]
        low = df["low"]
        close = df["close"].shift(1)

        tr = pd.concat([
            high - low,
            (high - close).abs(),
            (low - close).abs(),
        ], axis=1).max(axis=1)

        atr = tr.rolling(period).mean().iloc[-1]
        return float(atr) if not np.isnan(atr) else 0.0

    def _get_latest_swing_pair(
        self, swings: dict, direction: str
    ) -> tuple[Optional[float], Optional[float]]:
        """หา swing low/high คู่ล่าสุดสำหรับ draw Fibonacci
        คืน (swing_low_price, swing_high_price) เสมอ — draw_fib จัดการทิศตาม direction เอง
        ใช้ swing ล่าสุดของแต่ละฝั่งเพื่อ leg ที่สดใหม่ (ไม่ใช่ extreme ทั้งช่วง)
        """
        highs = [p for _, p in swings.get("highs", [])]
        lows = [p for _, p in swings.get("lows", [])]

        if not highs or not lows:
            return None, None

        swing_low = lows[-1]
        swing_high = highs[-1]
        # กันกรณี low/high สลับกัน ให้ค่าเรียงถูกเสมอ
        return min(swing_low, swing_high), max(swing_low, swing_high)

    def generate_signal(
        self,
        df_h1: pd.DataFrame,
        df_m15: pd.DataFrame,
        df_m5: pd.DataFrame,
    ) -> dict:
        """
        สร้าง trading signal จากข้อมูล 3 timeframe
        return dict: direction, fib_hit, fvg, choch, bos, confidence, entry, sl, tp, rr, reason
        """
        reason_parts: list[str] = []
        confidence: int = 0

        try:
            # ใช้ H1 หา structure หลัก
            swings_h1 = self.detect_swings(df_h1)
            choch, choch_dir = self.detect_choch(df_h1, swings_h1)
            bos, bos_dir = self.detect_bos(df_h1, swings_h1)

            # กำหนด direction จาก CHoCH หรือ BOS
            direction = ""
            if choch:
                direction = choch_dir
                confidence += 25
                reason_parts.append(f"✅ CHoCH ตรวจพบแนวโน้ม {direction} บน H1")
            else:
                reason_parts.append("❌ ไม่พบ CHoCH บน H1")

            if bos:
                if not direction:
                    direction = bos_dir
                confidence += 15
                reason_parts.append(f"✅ BOS ทะลุโครงสร้าง {bos_dir} บน H1")
            else:
                reason_parts.append("❌ ไม่พบ BOS บน H1")

            if not direction:
                direction = "BUY"  # default เมื่อไม่มี signal ชัด

            # วาด Fibonacci บน H1
            swing_low, swing_high = self._get_latest_swing_pair(swings_h1, direction)
            fib_prices: dict[float, float] = {}
            if swing_low and swing_high:
                fib_prices = self.draw_fib(swing_low, swing_high, direction)

            # ตรวจ FVG บน M15
            fvg_m15 = self.detect_fvg(df_m15)

            # ราคา entry = close ล่าสุดของ M5
            entry_price = float(df_m5["close"].iloc[-1])

            # ตรวจ Fib + FVG confluence
            fib_fvg_ok = False
            fib_hit_level: Optional[float] = None

            if fib_prices:
                fib_fvg_ok, fib_hit_level = self.check_fib_fvg_confluence(
                    entry_price, fib_prices, fvg_m15, direction
                )

            if fib_hit_level is not None:
                confidence += 30
                reason_parts.append(
                    f"✅ ราคาอยู่ใน Fib {fib_hit_level:.3f} golden zone"
                )
            else:
                reason_parts.append("❌ ราคายังไม่เข้า Fib entry zone (0.618-0.786)")

            if fib_fvg_ok:
                confidence += 30
                reason_parts.append("✅ FVG ซ้อนทับใน Fib zone บน M15")
            else:
                reason_parts.append("❌ ไม่มี FVG confluence ใน Fib zone")

            # คำนวณ ATR บน M5 สำหรับ SL
            atr = self.calculate_atr(df_m5)
            sl_distance = atr * ATR_SL_MULTIPLIER

            if direction == "BUY":
                sl = entry_price - sl_distance
                # TP อยู่ที่ Fib 0 (swing high) หรือ Fib 0.14
                tp_level = fib_prices.get(FIB_TP_LEVELS[0], entry_price + sl_distance * MIN_RR_RATIO)
                tp = tp_level if tp_level > entry_price else entry_price + sl_distance * MIN_RR_RATIO
            else:
                sl = entry_price + sl_distance
                tp_level = fib_prices.get(FIB_TP_LEVELS[0], entry_price - sl_distance * MIN_RR_RATIO)
                tp = tp_level if tp_level < entry_price else entry_price - sl_distance * MIN_RR_RATIO

            # คำนวณ R:R
            risk = abs(entry_price - sl)
            reward = abs(tp - entry_price)
            rr = round(reward / risk, 2) if risk > 0 else 0

            return {
                "direction":  direction,
                "fib_hit":    fib_hit_level,
                "fvg":        fib_fvg_ok,
                "choch":      choch,
                "bos":        bos,
                "confidence": min(confidence, 100),
                "entry":      round(entry_price, 2),
                "sl":         round(sl, 2),
                "tp":         round(tp, 2),
                "rr":         rr,
                "reason":     "\n".join(reason_parts),
                "tf":         "M5/M15/H1",
            }

        except Exception as e:
            logger.error(f"generate_signal error: {e}")
            return {
                "direction": "", "fib_hit": None, "fvg": False,
                "choch": False, "bos": False, "confidence": 0,
                "entry": 0, "sl": 0, "tp": 0, "rr": 0,
                "reason": f"Error: {e}", "tf": "",
            }
