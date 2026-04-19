"""
risk.py — จัดการความเสี่ยงก่อนส่ง order ทุกครั้ง
ตรวจสอบ lot size, daily loss, position ที่เปิดอยู่, และ R:R
"""
import logging
from config import RISK_PERCENT, MAX_DAILY_LOSS_PERCENT, MIN_RR_RATIO

logger = logging.getLogger(__name__)


class RiskManager:
    """ตรวจสอบเงื่อนไขความเสี่ยงก่อน execute trade"""

    def calculate_lot(
        self,
        account_balance: float,
        sl_pips: float,
        risk_percent: float = RISK_PERCENT,
        pip_value: float = 10.0,  # ค่า pip สำหรับ XAUUSD lot 1.0
    ) -> float:
        """
        คำนวณ lot size ตาม % ความเสี่ยงและ SL distance
        lot = (balance * risk%) / (sl_pips * pip_value)
        ปัดลงทศนิยม 2 ตำแหน่ง และไม่ต่ำกว่า 0.01
        """
        if sl_pips <= 0 or account_balance <= 0:
            logger.warning("calculate_lot: sl_pips หรือ balance ผิดปกติ")
            return 0.01

        risk_amount = account_balance * (risk_percent / 100)
        lot = risk_amount / (sl_pips * pip_value)
        lot = max(0.01, round(lot, 2))

        logger.info(
            f"Lot calc: balance={account_balance}, risk={risk_percent}%, "
            f"sl={sl_pips}pip → lot={lot}"
        )
        return lot

    def check_daily_loss(
        self,
        today_pnl: float,
        account_balance: float,
        max_percent: float = MAX_DAILY_LOSS_PERCENT,
    ) -> bool:
        """
        ตรวจว่า daily loss เกิน limit แล้วหรือยัง
        return True = ควรหยุดเทรด, False = ยังเทรดได้
        """
        if account_balance <= 0:
            return True

        loss_percent = abs(min(today_pnl, 0)) / account_balance * 100

        if loss_percent >= max_percent:
            logger.warning(
                f"Daily loss {loss_percent:.2f}% เกิน limit {max_percent}% — หยุดเทรด"
            )
            return True

        logger.debug(f"Daily loss {loss_percent:.2f}% ยังอยู่ในขอบเขต")
        return False

    def check_existing_position(self, positions: list) -> bool:
        """
        ตรวจว่ามี XAUUSD position เปิดอยู่แล้วหรือเปล่า
        return True = มี position อยู่ (ไม่ควรเปิดใหม่)
        """
        for pos in positions:
            symbol = getattr(pos, "symbol", "") or pos.get("symbol", "")
            if "XAUUSD" in str(symbol).upper() or "XAU" in str(symbol).upper():
                logger.info(f"พบ position เปิดอยู่: {symbol}")
                return True
        return False

    def validate_rr(
        self,
        entry: float,
        sl: float,
        tp: float,
        min_rr: float = MIN_RR_RATIO,
    ) -> bool:
        """
        ตรวจ R:R ว่าผ่านขั้นต่ำหรือไม่
        return True = RR ผ่าน, False = RR ต่ำเกินไป
        """
        risk = abs(entry - sl)
        reward = abs(tp - entry)

        if risk <= 0:
            logger.warning("validate_rr: risk = 0 ผิดปกติ")
            return False

        rr = reward / risk
        ok = rr >= min_rr

        logger.info(
            f"RR check: entry={entry}, sl={sl}, tp={tp} → RR={rr:.2f} "
            f"(min={min_rr}) {'✅' if ok else '❌'}"
        )
        return ok

    def validate_all(
        self,
        signal: dict,
        account_balance: float,
        today_pnl: float,
        open_positions: list,
    ) -> tuple[bool, str]:
        """
        รวมการตรวจทุกอย่างในครั้งเดียว
        return: (passed: bool, reason: str)
        """
        # หยุดเทรดถ้า daily loss เกิน
        if self.check_daily_loss(today_pnl, account_balance):
            return False, f"Daily loss เกิน {MAX_DAILY_LOSS_PERCENT}% — หยุดเทรดวันนี้"

        # มี position เปิดอยู่แล้ว
        if self.check_existing_position(open_positions):
            return False, "มี XAUUSD position เปิดอยู่ รอปิดก่อน"

        # RR ไม่ผ่าน
        if not self.validate_rr(
            signal.get("entry", 0),
            signal.get("sl", 0),
            signal.get("tp", 0),
        ):
            rr = signal.get("rr", 0)
            return False, f"RR {rr:.2f} ต่ำกว่าขั้นต่ำ {MIN_RR_RATIO}"

        return True, "ผ่านทุก risk check"
