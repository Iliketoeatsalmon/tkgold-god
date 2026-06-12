"""
obsidian_writer.py — เขียน trading journal ลง Obsidian vault
สร้างไฟล์ .md สำหรับแต่ละ trade, สรุปรายวัน, และ performance note
"""
from __future__ import annotations
import logging
import os
from datetime import datetime, date, timezone
from pathlib import Path
from config import OBSIDIAN_VAULT_PATH

logger = logging.getLogger(__name__)


class ObsidianWriter:
    """จัดการเขียน Markdown journal ลง Obsidian vault"""

    def __init__(self, vault_path: str = OBSIDIAN_VAULT_PATH) -> None:
        self.vault = Path(vault_path)
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """สร้าง folder structure ถ้ายังไม่มี"""
        for folder in ("trades", "daily", "strategy"):
            try:
                (self.vault / folder).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.warning(f"ไม่สามารถสร้าง folder {folder}: {e}")

    def _write(self, path: Path, content: str) -> None:
        """เขียนไฟล์ลง disk พร้อม error handling"""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            logger.info(f"เขียน Obsidian: {path}")
        except Exception as e:
            logger.error(f"เขียนไฟล์ล้มเหลว {path}: {e}")

    # ──────────────────────────────────────────────
    # Trade journal
    # ──────────────────────────────────────────────

    def write_trade_journal(
        self,
        order: dict,
        signal: dict,
        ai_analysis: str = "",
    ) -> None:
        """
        บันทึก trade journal ทีละ trade
        ไฟล์: trades/YYYY-MM-DD_XAUUSD_BUY.md
        """
        direction = order.get("direction", "")
        timestamp = order.get("timestamp", datetime.now(timezone.utc).isoformat())

        try:
            dt = datetime.fromisoformat(timestamp)
        except Exception:
            dt = datetime.now(timezone.utc)

        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%H:%M")
        month_str = dt.strftime("%d %b %Y")

        pnl = order.get("pnl", 0) or 0
        result_tag = "WIN" if pnl > 0 else "LOSS"
        fib_level = signal.get("fib_hit") or ""
        fib_tag = f"#Fib{str(fib_level).replace('.', '')}" if fib_level else ""

        # checklist items
        fib_check = "x" if signal.get("fib_hit") else " "
        fvg_check = "x" if signal.get("fvg") else " "
        choch_check = "x" if signal.get("choch") else " "
        bos_check = "x" if signal.get("bos") else " "

        content = f"""# XAUUSD {direction} — {month_str} {time_str}

## Setup Checklist
- [{fib_check}] Fib {fib_level} hit
- [{fvg_check}] FVG confluence
- [{choch_check}] CHoCH confirm
- [{bos_check}] BOS break

## Entry Details
| Entry | SL | TP | R:R |
|-------|----|----|-----|
| {order.get('entry', '')} | {order.get('sl', '')} | {order.get('tp', '')} | {signal.get('rr', '')} |

## Result
PnL: {"+" if pnl >= 0 else ""}{pnl:.2f} USD
Status: {order.get('status', '')}
Close Price: {order.get('close_price', 'ยังไม่ปิด')}

## Reason
{signal.get('reason', '')}

## AI Analysis
{ai_analysis if ai_analysis else '_ยังไม่ได้วิเคราะห์_'}

## Tags
#XAUUSD #SMC #{result_tag} {fib_tag}
"""

        filename = f"{date_str}_XAUUSD_{direction}.md"
        self._write(self.vault / "trades" / filename, content)

    # ──────────────────────────────────────────────
    # Daily summary
    # ──────────────────────────────────────────────

    def write_daily_summary(
        self,
        target_date: date,
        stats: dict,
        trades: list[dict] | None = None,
    ) -> None:
        """
        สร้างสรุปรายวัน
        ไฟล์: daily/YYYY-MM-DD.md
        """
        date_str = target_date.isoformat()
        pnl = stats.get("pnl", 0)
        total = stats.get("total_trades", 0)
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        win_rate = round(wins / total * 100, 1) if total else 0
        stopped = "⛔ หยุดเทรดเพราะ daily loss" if stats.get("stopped") else "✅ เทรดปกติ"

        # รายการ trade วันนี้
        trade_lines = ""
        if trades:
            rows = []
            for t in trades:
                pnl_t = t.get("pnl", 0) or 0
                icon = "🟢" if pnl_t > 0 else "🔴"
                rows.append(
                    f"| {icon} | {t.get('direction','')} | {t.get('entry','')} | "
                    f"{t.get('close_price','')} | {pnl_t:+.2f} |"
                )
            trade_lines = "\n".join(rows)

        content = f"""# Daily Summary — {date_str}

## สถานะ
{stopped}

## สรุปผล
| รายการ | ค่า |
|--------|-----|
| จำนวน trades | {total} |
| Win | {wins} |
| Loss | {losses} |
| Win Rate | {win_rate}% |
| PnL รวม | {"+" if pnl >= 0 else ""}{pnl:.2f} USD |
| Max Drawdown | {stats.get('drawdown', 0):.2f} USD |

## รายการ Trades
| | Direction | Entry | Close | PnL |
|--|-----------|-------|-------|-----|
{trade_lines}

## Tags
#DailySummary #XAUUSD #{date_str}
"""

        self._write(self.vault / "daily" / f"{date_str}.md", content)

    # ──────────────────────────────────────────────
    # Strategy performance
    # ──────────────────────────────────────────────

    def write_strategy_note(self, ai_progress: dict) -> None:
        """
        อัปเดต strategy/performance.md ด้วย AI progress ล่าสุด
        """
        version = ai_progress.get("version", 1)
        timestamp = ai_progress.get("timestamp", datetime.now(timezone.utc).isoformat())
        win_rate = ai_progress.get("win_rate", 0)
        total = ai_progress.get("total_trades", 0)
        total_pnl = ai_progress.get("total_pnl", 0)
        sharpe = ai_progress.get("sharpe", 0)
        max_dd = ai_progress.get("max_drawdown", 0)
        note = ai_progress.get("note", "")

        perf_path = self.vault / "strategy" / "performance.md"

        # อ่าน existing content ถ้ามี
        existing = ""
        if perf_path.exists():
            try:
                existing = perf_path.read_text(encoding="utf-8")
            except Exception:
                pass

        new_entry = f"""
---
## Version {version} — {timestamp}
| Metric | Value |
|--------|-------|
| Win Rate | {win_rate}% |
| Total Trades | {total} |
| Total PnL | {"+" if total_pnl >= 0 else ""}{total_pnl:.2f} USD |
| Sharpe Ratio | {sharpe} |
| Max Drawdown | {max_dd:.2f} USD |

Note: {note}
"""

        # prepend entry ใหม่ต่อจาก header เดิม
        if "# Strategy Performance" in existing:
            content = existing.replace(
                "# Strategy Performance\n",
                f"# Strategy Performance\n{new_entry}"
            )
        else:
            content = f"# Strategy Performance\n{new_entry}\n{existing}"

        self._write(perf_path, content)
