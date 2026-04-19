"""
db.py — จัดการ SQLite database ทั้งหมดของระบบ
สร้างตาราง, บันทึก, อ่านข้อมูล signals/orders/ai_progress/daily_stats
"""
import sqlite3
import logging
from datetime import date, datetime
from typing import Optional
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """เปิด connection พร้อม row_factory เพื่อ return dict"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # รองรับ concurrent read/write
    return conn


def init_db() -> None:
    """สร้างตารางทั้งหมดถ้ายังไม่มี"""
    conn = get_connection()
    try:
        cur = conn.cursor()

        # ตาราง signals — บันทึก signal ที่ generate ได้จาก strategy
        cur.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                tf          TEXT NOT NULL,
                direction   TEXT NOT NULL,
                fib_hit     REAL,
                fvg         INTEGER DEFAULT 0,
                choch       INTEGER DEFAULT 0,
                bos         INTEGER DEFAULT 0,
                confidence  INTEGER DEFAULT 0,
                entry       REAL,
                sl          REAL,
                tp          REAL,
                rr          REAL,
                reason      TEXT,
                executed    INTEGER DEFAULT 0,
                broker      TEXT DEFAULT ''
            )
        """)

        # ตาราง orders — บันทึก order ที่ส่งไปยัง broker
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    TEXT NOT NULL,
                broker       TEXT NOT NULL,
                symbol       TEXT NOT NULL,
                direction    TEXT NOT NULL,
                lot          REAL,
                entry        REAL,
                sl           REAL,
                tp           REAL,
                close_price  REAL,
                pnl          REAL,
                status       TEXT DEFAULT 'open',
                metaapi_id   TEXT,
                signal_id    INTEGER,
                FOREIGN KEY (signal_id) REFERENCES signals(id)
            )
        """)

        # ตาราง ai_progress — บันทึกผลประเมิน AI แต่ละ version
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_progress (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    TEXT NOT NULL,
                version      INTEGER NOT NULL,
                win_rate     REAL,
                total_trades INTEGER,
                total_pnl    REAL,
                sharpe       REAL,
                max_drawdown REAL,
                note         TEXT
            )
        """)

        # ตาราง daily_stats — สรุปผลรายวัน
        cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                date         TEXT NOT NULL UNIQUE,
                total_trades INTEGER DEFAULT 0,
                wins         INTEGER DEFAULT 0,
                losses       INTEGER DEFAULT 0,
                pnl          REAL DEFAULT 0,
                drawdown     REAL DEFAULT 0,
                stopped      INTEGER DEFAULT 0
            )
        """)

        conn.commit()
        logger.info("DB initialized สำเร็จ")
    except Exception as e:
        logger.error(f"init_db error: {e}")
        raise
    finally:
        conn.close()


def save_signal(signal: dict) -> int:
    """บันทึก signal ลง DB และ return id"""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO signals
                (timestamp, tf, direction, fib_hit, fvg, choch, bos,
                 confidence, entry, sl, tp, rr, reason, executed, broker)
            VALUES
                (:timestamp, :tf, :direction, :fib_hit, :fvg, :choch, :bos,
                 :confidence, :entry, :sl, :tp, :rr, :reason, :executed, :broker)
        """, {
            "timestamp":  signal.get("timestamp", datetime.utcnow().isoformat()),
            "tf":         signal.get("tf", ""),
            "direction":  signal.get("direction", ""),
            "fib_hit":    signal.get("fib_hit"),
            "fvg":        int(signal.get("fvg", False)),
            "choch":      int(signal.get("choch", False)),
            "bos":        int(signal.get("bos", False)),
            "confidence": signal.get("confidence", 0),
            "entry":      signal.get("entry"),
            "sl":         signal.get("sl"),
            "tp":         signal.get("tp"),
            "rr":         signal.get("rr"),
            "reason":     signal.get("reason", ""),
            "executed":   int(signal.get("executed", False)),
            "broker":     signal.get("broker", ""),
        })
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        logger.error(f"save_signal error: {e}")
        raise
    finally:
        conn.close()


def save_order(order: dict) -> int:
    """บันทึก order ใหม่ลง DB"""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO orders
                (timestamp, broker, symbol, direction, lot, entry,
                 sl, tp, close_price, pnl, status, metaapi_id, signal_id)
            VALUES
                (:timestamp, :broker, :symbol, :direction, :lot, :entry,
                 :sl, :tp, :close_price, :pnl, :status, :metaapi_id, :signal_id)
        """, {
            "timestamp":   order.get("timestamp", datetime.utcnow().isoformat()),
            "broker":      order.get("broker", ""),
            "symbol":      order.get("symbol", "XAUUSD"),
            "direction":   order.get("direction", ""),
            "lot":         order.get("lot", 0),
            "entry":       order.get("entry"),
            "sl":          order.get("sl"),
            "tp":          order.get("tp"),
            "close_price": order.get("close_price"),
            "pnl":         order.get("pnl"),
            "status":      order.get("status", "open"),
            "metaapi_id":  order.get("metaapi_id", ""),
            "signal_id":   order.get("signal_id"),
        })
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        logger.error(f"save_order error: {e}")
        raise
    finally:
        conn.close()


def update_order(order_id: int, updates: dict) -> None:
    """อัปเดต field ใน order (status, pnl, close_price ฯลฯ)"""
    if not updates:
        return
    conn = get_connection()
    try:
        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        updates["order_id"] = order_id
        conn.execute(
            f"UPDATE orders SET {set_clause} WHERE id = :order_id",
            updates
        )
        conn.commit()
    except Exception as e:
        logger.error(f"update_order error: {e}")
        raise
    finally:
        conn.close()


def save_ai_progress(progress: dict) -> int:
    """บันทึกผล AI progress version ใหม่"""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ai_progress
                (timestamp, version, win_rate, total_trades, total_pnl,
                 sharpe, max_drawdown, note)
            VALUES
                (:timestamp, :version, :win_rate, :total_trades, :total_pnl,
                 :sharpe, :max_drawdown, :note)
        """, {
            "timestamp":    datetime.utcnow().isoformat(),
            "version":      progress.get("version", 1),
            "win_rate":     progress.get("win_rate", 0),
            "total_trades": progress.get("total_trades", 0),
            "total_pnl":    progress.get("total_pnl", 0),
            "sharpe":       progress.get("sharpe", 0),
            "max_drawdown": progress.get("max_drawdown", 0),
            "note":         progress.get("note", ""),
        })
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        logger.error(f"save_ai_progress error: {e}")
        raise
    finally:
        conn.close()


def get_today_stats() -> dict:
    """ดึงสถิติของวันนี้จาก daily_stats"""
    today = date.today().isoformat()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM daily_stats WHERE date = ?", (today,)
        ).fetchone()
        if row:
            return dict(row)
        return {
            "date": today, "total_trades": 0, "wins": 0,
            "losses": 0, "pnl": 0.0, "drawdown": 0.0, "stopped": 0
        }
    finally:
        conn.close()


def upsert_daily_stats(stats: dict) -> None:
    """บันทึกหรืออัปเดตสถิติรายวัน"""
    today = date.today().isoformat()
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO daily_stats (date, total_trades, wins, losses, pnl, drawdown, stopped)
            VALUES (:date, :total_trades, :wins, :losses, :pnl, :drawdown, :stopped)
            ON CONFLICT(date) DO UPDATE SET
                total_trades = excluded.total_trades,
                wins         = excluded.wins,
                losses       = excluded.losses,
                pnl          = excluded.pnl,
                drawdown     = excluded.drawdown,
                stopped      = excluded.stopped
        """, {**{"date": today, "total_trades": 0, "wins": 0, "losses": 0,
                 "pnl": 0, "drawdown": 0, "stopped": 0}, **stats})
        conn.commit()
    finally:
        conn.close()


def get_equity_curve(limit: int = 100) -> list[dict]:
    """ดึง equity curve จาก closed orders เรียง timestamp"""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT timestamp, SUM(pnl) OVER (ORDER BY id) AS equity, pnl
            FROM orders
            WHERE status = 'closed' AND pnl IS NOT NULL
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in reversed(rows)]
    finally:
        conn.close()


def get_signals(limit: int = 50) -> list[dict]:
    """ดึง signals ล่าสุด"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_orders(limit: int = 50, status: str = "all") -> list[dict]:
    """ดึง orders กรองตาม status"""
    conn = get_connection()
    try:
        if status == "all":
            rows = conn.execute(
                "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM orders WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_order_stats() -> dict:
    """สถิติ order: win rate, total pnl, best/worst trade"""
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) AS losses,
                ROUND(SUM(pnl), 2) AS total_pnl,
                ROUND(MAX(pnl), 2) AS best_trade,
                ROUND(MIN(pnl), 2) AS worst_trade
            FROM orders WHERE status = 'closed' AND pnl IS NOT NULL
        """).fetchone()
        d = dict(row)
        d["win_rate"] = (
            round(d["wins"] / d["total"] * 100, 1) if d["total"] else 0
        )
        return d
    finally:
        conn.close()


def get_ai_progress(limit: int = 50) -> list[dict]:
    """ดึง AI progress history"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM ai_progress ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_signal_by_id(signal_id: int) -> Optional[dict]:
    """ดึง signal เดี่ยวตาม id"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM signals WHERE id = ?", (signal_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_daily_stats_history(limit: int = 30) -> list[dict]:
    """ดึงสถิติรายวัน 30 วันล่าสุด"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM daily_stats ORDER BY date DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
