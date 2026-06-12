"""
bot.py — หัวใจหลักของระบบ รัน trading loop
broker backend (MetaApi/MT5) เลือกผ่าน BROKER_BACKEND ใน .env
รองรับ graceful shutdown ด้วย Ctrl+C และ auto-reconnect
"""
import asyncio
import logging
import signal
import sys
from datetime import datetime, date, timezone
from typing import Optional

import pandas as pd

from config import (
    SYMBOL,
    LOT_SIZE, LOOP_INTERVAL_SECONDS, MIN_CONFIDENCE,
    CANDLE_BARS, AI_PROGRESS_CYCLE,
)
import db
from broker import broker
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
        self.broker = broker  # backend เลือกจาก BROKER_BACKEND
        self.running = False
        self.cycle_count = 0
        self.current_signal: dict = {}
        self.account_info: dict = {}

    # ──────────────────────────────────────────────
    # Broker connection (delegate ไป broker layer)
    # ──────────────────────────────────────────────

    async def connect(self) -> None:
        """เชื่อม broker — raise ถ้าไม่สำเร็จ"""
        ok = await self.broker.connect()
        if not ok:
            raise RuntimeError("เชื่อม broker ไม่สำเร็จ — เช็ค config/credentials")

    async def get_candles(self, tf: str, bars: int = CANDLE_BARS) -> pd.DataFrame:
        """ดึง candle data เป็น DataFrame"""
        df = await self.broker.get_candles(tf, bars)
        logger.debug(f"ดึง {len(df)} candles [{tf}]")
        return df

    async def get_account_info(self) -> dict:
        """ดึง balance, equity, floating pnl"""
        info = await self.broker.get_account_info()
        if info:
            self.account_info = info
        return self.account_info

    async def get_open_positions(self) -> list:
        """ดึง positions ที่ยังเปิดอยู่"""
        return await self.broker.get_open_positions()

    # ──────────────────────────────────────────────
    # Order management
    # ──────────────────────────────────────────────

    async def place_order(self, signal: dict, lot: float) -> Optional[dict]:
        """ส่ง market order พร้อม SL/TP ไปยัง broker"""
        direction = signal["direction"]
        result = await self.broker.place_market_order(
            direction, lot, signal["sl"], signal["tp"]
        )
        if result:
            logger.info(f"✅ Order ส่งสำเร็จ: {direction} {lot} lots @ {signal['entry']}")
        return result

    async def close_position(self, position_id: str) -> bool:
        """ปิด position ตาม id"""
        ok = await self.broker.close_position(position_id)
        if ok:
            logger.info(f"ปิด position {position_id} สำเร็จ")
        return ok

    # ──────────────────────────────────────────────
    # Order reconciliation (sync broker → DB)
    # ──────────────────────────────────────────────

    async def reconcile_orders(self) -> None:
        """sync order ที่ปิดที่ broker กลับเข้า DB + อัปเดต pnl และ daily stats"""
        try:
            open_orders = db.get_orders(limit=1000, status="open")
            if not open_orders:
                return

            positions = await self.get_open_positions()
            live_ids = set()
            for p in positions:
                pid = getattr(p, "id", None)
                if pid is None and isinstance(p, dict):
                    pid = p.get("id")
                if pid is not None:
                    live_ids.add(str(pid))

            # order ที่ DB ว่า open แต่ broker ไม่มีแล้ว = ปิดไปแล้ว
            for o in open_orders:
                mid = str(o.get("metaapi_id") or "")
                if mid and mid not in live_ids:
                    pnl, close_price = await self._fetch_closed_pnl(mid)
                    db.update_order(o["id"], {
                        "status":      "closed",
                        "pnl":         pnl,
                        "close_price": close_price,
                    })
                    logger.info(f"Order {o['id']} ปิดแล้ว pnl={pnl}")

            self._refresh_daily_stats()

        except Exception as e:
            logger.error(f"reconcile_orders error: {e}")

    async def _fetch_closed_pnl(self, position_id: str) -> tuple[float, Optional[float]]:
        """ดึง pnl รวมของ position ที่ปิดแล้วจาก deals (best-effort)"""
        try:
            deals = await self.broker.get_deals_by_position(position_id)
            pnl = sum(d["profit"] for d in deals)
            close_price = deals[-1]["price"] if deals else None
            return round(pnl, 2), close_price
        except Exception as e:
            logger.warning(f"_fetch_closed_pnl error ({position_id}): {e}")
            return 0.0, None

    def _refresh_daily_stats(self) -> None:
        """คำนวณสถิติวันนี้จาก closed orders แล้ว upsert (ใช้กับ daily loss limit)"""
        try:
            today = date.today().isoformat()
            closed = db.get_orders(limit=1000, status="closed")
            todays = [o for o in closed if str(o.get("timestamp", "")).startswith(today)]
            wins = sum(1 for o in todays if (o.get("pnl") or 0) > 0)
            losses = sum(1 for o in todays if (o.get("pnl") or 0) <= 0)
            pnl = round(sum((o.get("pnl") or 0) for o in todays), 2)
            db.upsert_daily_stats({
                "total_trades": len(todays),
                "wins":         wins,
                "losses":       losses,
                "pnl":          pnl,
            })
        except Exception as e:
            logger.error(f"_refresh_daily_stats error: {e}")

    # ──────────────────────────────────────────────
    # AI analysis (Claude / local model)
    # ──────────────────────────────────────────────

    async def get_ai_analysis(self, signal: dict) -> str:
        """วิเคราะห์ signal เป็นภาษาไทย ผ่าน AI provider ที่ตั้งค่าไว้ (Claude หรือ local)"""
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

        try:
            import ai
            # ai.analyze เป็น blocking I/O — รันใน thread แยกไม่ให้ block event loop
            return await asyncio.to_thread(ai.analyze, prompt, 800)
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
                signal["timestamp"] = datetime.now(timezone.utc).isoformat()
                self.current_signal = signal

                logger.info(
                    f"Signal: {signal['direction']} confidence={signal['confidence']}% "
                    f"entry={signal['entry']} sl={signal['sl']} tp={signal['tp']}"
                )

                # 3. บันทึก signal ลง DB
                signal_id = db.save_signal(signal)

                # 3.5 sync order ที่ปิดที่ broker + refresh daily stats (ก่อนเช็ค risk)
                await self.reconcile_orders()

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

                        # mark signal as executed (อยู่ตาราง signals ไม่ใช่ orders)
                        db.update_signal(signal_id, {"executed": 1})

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
