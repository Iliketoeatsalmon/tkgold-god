"""
bot.py — หัวใจหลักของระบบ เชื่อม MetaApi และรัน trading loop
รองรับ graceful shutdown ด้วย Ctrl+C และ auto-reconnect
"""
import asyncio
import logging
import signal
import sys
from datetime import datetime, date
from typing import Optional

import pandas as pd

from config import (
    METAAPI_TOKEN, ACCOUNT_ID, SYMBOL,
    LOT_SIZE, LOOP_INTERVAL_SECONDS, MIN_CONFIDENCE,
    CANDLE_BARS, METAAPI_RETRY_DELAY, METAAPI_MAX_RETRIES,
    AI_PROGRESS_CYCLE, ANTHROPIC_API_KEY,
)
import db
from strategy import SMCStrategy
from risk import RiskManager
from obsidian_writer import ObsidianWriter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


class XAUBot:
    """XAUUSD SMC Trading Bot"""

    def __init__(self) -> None:
        self.strategy = SMCStrategy()
        self.risk = RiskManager()
        self.obsidian = ObsidianWriter()
        self.connection = None
        self.api = None
        self.account = None
        self.running = False
        self.cycle_count = 0
        self.current_signal: dict = {}
        self.account_info: dict = {}

    # ──────────────────────────────────────────────
    # MetaApi connection
    # ──────────────────────────────────────────────

    async def connect(self) -> None:
        """เชื่อม MetaApi พร้อม retry อัตโนมัติ"""
        from metaapi_cloud_sdk import MetaApi  # type: ignore

        for attempt in range(1, METAAPI_MAX_RETRIES + 1):
            try:
                logger.info(f"เชื่อม MetaApi... (ครั้งที่ {attempt})")
                self.api = MetaApi(METAAPI_TOKEN)
                self.account = await self.api.metatrader_account_api.get_account(ACCOUNT_ID)

                # รอ account deploy
                if self.account.state not in ("DEPLOYED", "DEPLOYING"):
                    await self.account.deploy()
                await self.account.wait_connected()

                self.connection = self.account.get_rpc_connection()
                await self.connection.connect()
                await self.connection.wait_synchronized()

                logger.info("✅ เชื่อม MetaApi สำเร็จ")
                return

            except Exception as e:
                logger.error(f"เชื่อม MetaApi ล้มเหลว: {e}")
                if attempt < METAAPI_MAX_RETRIES:
                    logger.info(f"รอ {METAAPI_RETRY_DELAY}s แล้วลองใหม่...")
                    await asyncio.sleep(METAAPI_RETRY_DELAY)
                else:
                    raise RuntimeError(
                        f"เชื่อม MetaApi ไม่ได้หลัง {METAAPI_MAX_RETRIES} ครั้ง"
                    )

    async def _ensure_connected(self) -> None:
        """ตรวจ connection ถ้าหลุดให้ reconnect"""
        try:
            if self.connection is None or not self.connection.synchronized:
                logger.warning("Connection หลุด — กำลัง reconnect...")
                await self.connect()
        except Exception as e:
            logger.error(f"_ensure_connected error: {e}")
            raise

    # ──────────────────────────────────────────────
    # ดึงข้อมูล market
    # ──────────────────────────────────────────────

    async def get_candles(self, tf: str, bars: int = CANDLE_BARS) -> pd.DataFrame:
        """ดึง candle data จาก MetaApi แปลงเป็น DataFrame"""
        await self._ensure_connected()

        # map timeframe string → MetaApi format
        tf_map = {"1h": "1h", "15min": "15m", "5min": "5m", "H1": "1h", "M15": "15m", "M5": "5m"}
        api_tf = tf_map.get(tf, tf)

        candles = await self.connection.get_historical_candles(
            SYMBOL, api_tf, datetime.utcnow(), bars
        )

        rows = []
        for c in candles:
            rows.append({
                "time":  c.get("time"),
                "open":  float(c.get("open", 0)),
                "high":  float(c.get("high", 0)),
                "low":   float(c.get("low", 0)),
                "close": float(c.get("close", 0)),
                "volume": float(c.get("tickVolume", 0)),
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df["time"] = pd.to_datetime(df["time"])
            df.sort_values("time", inplace=True)
            df.reset_index(drop=True, inplace=True)

        logger.debug(f"ดึง {len(df)} candles [{tf}]")
        return df

    async def get_account_info(self) -> dict:
        """ดึง balance, equity, floating pnl"""
        await self._ensure_connected()
        try:
            info = await self.connection.get_account_information()
            result = {
                "balance":  float(info.get("balance", 0)),
                "equity":   float(info.get("equity", 0)),
                "floating": float(info.get("equity", 0)) - float(info.get("balance", 0)),
                "currency": info.get("currency", "USD"),
                "broker":   info.get("broker", ""),
                "server":   info.get("server", ""),
            }
            self.account_info = result
            return result
        except Exception as e:
            logger.error(f"get_account_info error: {e}")
            return self.account_info  # return cached ถ้า error

    async def get_open_positions(self) -> list:
        """ดึง positions ที่ยังเปิดอยู่"""
        await self._ensure_connected()
        try:
            return await self.connection.get_positions()
        except Exception as e:
            logger.error(f"get_open_positions error: {e}")
            return []

    # ──────────────────────────────────────────────
    # Order management
    # ──────────────────────────────────────────────

    async def place_order(self, signal: dict, lot: float) -> Optional[dict]:
        """ส่ง market order พร้อม SL/TP ไปยัง broker"""
        await self._ensure_connected()

        try:
            direction = signal["direction"]
            entry = signal["entry"]
            sl = signal["sl"]
            tp = signal["tp"]

            if direction == "BUY":
                result = await self.connection.create_market_buy_order(
                    SYMBOL, lot, sl, tp,
                    {"comment": "SMC-AI-Bot", "clientId": "xaubot"}
                )
            else:
                result = await self.connection.create_market_sell_order(
                    SYMBOL, lot, sl, tp,
                    {"comment": "SMC-AI-Bot", "clientId": "xaubot"}
                )

            logger.info(f"✅ Order ส่งสำเร็จ: {direction} {lot} lots @ {entry}")
            return result

        except Exception as e:
            logger.error(f"place_order error: {e}")
            return None

    async def close_position(self, position_id: str) -> bool:
        """ปิด position ตาม id"""
        await self._ensure_connected()
        try:
            await self.connection.close_position(position_id)
            logger.info(f"ปิด position {position_id} สำเร็จ")
            return True
        except Exception as e:
            logger.error(f"close_position error: {e}")
            return False

    # ──────────────────────────────────────────────
    # AI analysis (Claude)
    # ──────────────────────────────────────────────

    async def get_ai_analysis(self, signal: dict) -> str:
        """เรียก Claude API วิเคราะห์ signal เป็นภาษาไทย"""
        if not ANTHROPIC_API_KEY:
            return "ไม่มี ANTHROPIC_API_KEY"

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

            prompt = f"""วิเคราะห์ signal XAUUSD นี้เป็นภาษาไทย:

Direction: {signal.get('direction')}
Confidence: {signal.get('confidence')}%
Entry: {signal.get('entry')}
SL: {signal.get('sl')}
TP: {signal.get('tp')}
R:R: {signal.get('rr')}
Fib Level Hit: {signal.get('fib_hit')}
FVG: {signal.get('fvg')}
CHoCH: {signal.get('choch')}
BOS: {signal.get('bos')}

เหตุผล:
{signal.get('reason')}

กรุณาวิเคราะห์ว่า setup นี้ดีหรือไม่ มีความเสี่ยงอะไร และแนะนำการจัดการ trade"""

            message = client.messages.create(
                model="claude-opus-4-7",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text

        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return f"วิเคราะห์ไม่ได้: {e}"

    # ──────────────────────────────────────────────
    # AI progress calculation
    # ──────────────────────────────────────────────

    async def _update_ai_progress(self) -> None:
        """คำนวณและบันทึก AI progress จาก closed orders"""
        try:
            stats = db.get_order_stats()
            total = stats.get("total", 0)
            if total == 0:
                return

            wins = stats.get("wins", 0)
            total_pnl = stats.get("total_pnl", 0)
            win_rate = stats.get("win_rate", 0)

            # Sharpe ratio อย่างง่าย (PnL / std ของ individual trades)
            orders = db.get_orders(limit=1000, status="closed")
            pnls = [o["pnl"] for o in orders if o.get("pnl") is not None]
            import numpy as np
            sharpe = (
                round(float(np.mean(pnls)) / float(np.std(pnls)), 2)
                if len(pnls) > 1 and np.std(pnls) > 0
                else 0
            )

            # Max drawdown
            equity = 0
            peak = 0
            max_dd = 0
            for p in pnls:
                equity += p
                peak = max(peak, equity)
                dd = peak - equity
                max_dd = max(max_dd, dd)

            # version = จำนวน progress records ที่มี + 1
            current = db.get_ai_progress(limit=1)
            version = (current[0]["version"] + 1) if current else 1

            db.save_ai_progress({
                "version":      version,
                "win_rate":     win_rate,
                "total_trades": total,
                "total_pnl":    total_pnl,
                "sharpe":       sharpe,
                "max_drawdown": round(max_dd, 2),
                "note":         f"Auto update cycle {self.cycle_count}",
            })

            logger.info(
                f"AI Progress v{version}: WR={win_rate}%, PnL={total_pnl}, Sharpe={sharpe}"
            )

        except Exception as e:
            logger.error(f"_update_ai_progress error: {e}")

    # ──────────────────────────────────────────────
    # Main loop
    # ──────────────────────────────────────────────

    async def run_loop(self) -> None:
        """วนลูป trading หลัก"""
        self.running = True
        logger.info("🚀 Bot เริ่มทำงาน")

        await self.connect()
        db.init_db()

        while self.running:
            try:
                self.cycle_count += 1
                logger.info(f"── Cycle {self.cycle_count} ──────────────────")

                # 1. ดึงข้อมูล candles 3 timeframe
                df_h1, df_m15, df_m5 = await asyncio.gather(
                    self.get_candles("1h"),
                    self.get_candles("15min"),
                    self.get_candles("5min"),
                )

                if df_h1.empty or df_m15.empty or df_m5.empty:
                    logger.warning("ข้อมูล candles ว่าง ข้ามรอบนี้")
                    await asyncio.sleep(LOOP_INTERVAL_SECONDS)
                    continue

                # 2. สร้าง signal จาก SMC strategy
                signal = self.strategy.generate_signal(df_h1, df_m15, df_m5)
                signal["timestamp"] = datetime.utcnow().isoformat()
                self.current_signal = signal

                logger.info(
                    f"Signal: {signal['direction']} confidence={signal['confidence']}% "
                    f"entry={signal['entry']} sl={signal['sl']} tp={signal['tp']}"
                )

                # 3. บันทึก signal ลง DB
                signal_id = db.save_signal(signal)

                # 4. ตรวจ risk conditions
                account = await self.get_account_info()
                positions = await self.get_open_positions()
                today_stats = db.get_today_stats()
                today_pnl = today_stats.get("pnl", 0)

                passed, risk_reason = self.risk.validate_all(
                    signal, account["balance"], today_pnl, positions
                )

                logger.info(f"Risk check: {'✅' if passed else '❌'} {risk_reason}")

                # 5. ส่ง order ถ้าผ่านทุกเงื่อนไข
                if passed and signal["confidence"] >= MIN_CONFIDENCE and signal["direction"]:
                    # คำนวณ lot ตามความเสี่ยง
                    sl_pips = abs(signal["entry"] - signal["sl"]) / 0.1  # XAUUSD 0.1 = 1 pip
                    lot = self.risk.calculate_lot(account["balance"], sl_pips)

                    order_result = await self.place_order(signal, lot)

                    if order_result:
                        order_id = db.save_order({
                            "broker":     account.get("broker", ""),
                            "symbol":     SYMBOL,
                            "direction":  signal["direction"],
                            "lot":        lot,
                            "entry":      signal["entry"],
                            "sl":         signal["sl"],
                            "tp":         signal["tp"],
                            "status":     "open",
                            "metaapi_id": str(order_result.get("orderId", "")),
                            "signal_id":  signal_id,
                        })

                        # mark signal as executed
                        db.update_order(signal_id, {"executed": 1})

                        logger.info(f"✅ Order บันทึก DB id={order_id}")

                # 6. ทุก 10 cycle คำนวณ AI progress
                if self.cycle_count % AI_PROGRESS_CYCLE == 0:
                    await self._update_ai_progress()

                # รอรอบถัดไป
                await asyncio.sleep(LOOP_INTERVAL_SECONDS)

            except asyncio.CancelledError:
                logger.info("Loop ถูก cancel — กำลังหยุด...")
                break
            except Exception as e:
                logger.error(f"Loop error: {e}", exc_info=True)
                await asyncio.sleep(LOOP_INTERVAL_SECONDS)

        logger.info("Bot หยุดทำงานแล้ว")

    def stop(self) -> None:
        """หยุด bot อย่างปลอดภัย"""
        self.running = False
        logger.info("รับคำสั่ง stop")


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

async def main() -> None:
    bot = XAUBot()

    loop = asyncio.get_running_loop()

    def _shutdown(sig_name: str) -> None:
        logger.info(f"รับสัญญาณ {sig_name} — กำลัง shutdown...")
        bot.stop()
        for task in asyncio.all_tasks(loop):
            task.cancel()

    # รองรับ SIGINT (Ctrl+C) และ SIGTERM
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: _shutdown(s.name))
        except NotImplementedError:
            # Windows ไม่รองรับ add_signal_handler — ใช้ KeyboardInterrupt แทน
            pass

    try:
        await bot.run_loop()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt — หยุด bot")
        bot.stop()
    finally:
        logger.info("Cleanup เสร็จ")


if __name__ == "__main__":
    asyncio.run(main())
