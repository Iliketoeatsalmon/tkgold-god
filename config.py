"""
config.py — การตั้งค่าทั้งหมดของระบบ XAUUSD SMC AI Trading
โหลดจาก .env ก่อน ถ้าไม่มีใช้ค่า default
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Broker backend ───────────────────────────────
# "metaapi" = cloud (เสียเงิน), "mt5" = MetaTrader5 terminal บน Windows (ฟรี)
BROKER_BACKEND: str = os.getenv("BROKER_BACKEND", "metaapi")

# MetaApi credentials
METAAPI_TOKEN: str = os.getenv("METAAPI_TOKEN", "")
ACCOUNT_ID: str = os.getenv("ACCOUNT_ID", "")

# MT5 direct (Windows เท่านั้น) — เว้นว่าง login/password/server
# ถ้า MT5 terminal login ค้างไว้อยู่แล้ว (จะ attach เข้า terminal ที่เปิดอยู่)
MT5_LOGIN: str = os.getenv("MT5_LOGIN", "")
MT5_PASSWORD: str = os.getenv("MT5_PASSWORD", "")
MT5_SERVER: str = os.getenv("MT5_SERVER", "")
MT5_TERMINAL_PATH: str = os.getenv("MT5_TERMINAL_PATH", "")  # path terminal64.exe (optional)

# สัญลักษณ์และ timeframe ที่ใช้วิเคราะห์
# บาง broker ใช้ชื่อต่างกัน เช่น XAUUSDm, GOLD — override ผ่าน .env ได้
SYMBOL: str = os.getenv("SYMBOL", "XAUUSD")
TIMEFRAMES: list[str] = ["1h", "15min", "5min"]

# การจัดการขนาด lot และความเสี่ยง
LOT_SIZE: float = 0.01
RISK_PERCENT: float = 1.0          # เสี่ยงต่อ trade ไม่เกิน 1% ของ balance
MAX_DAILY_LOSS_PERCENT: float = 3.0  # หยุดเทรดถ้า daily loss เกิน 3%

# ระดับ Fibonacci ที่ใช้วาดและวิเคราะห์
FIB_LEVELS: list[float] = [0, 0.1, 0.14, 0.52, 0.57, 0.618, 0.786, 1]

# โซน entry ที่ต้องการ (golden zone)
FIB_ENTRY_ZONE: tuple[float, float] = (0.618, 0.786)

# ระดับ TP บน Fibonacci
FIB_TP_LEVELS: list[float] = [0, 0.14]

# SL คิดจาก ATR
ATR_SL_MULTIPLIER: float = 1.5

# R:R ขั้นต่ำที่ยอมรับ
MIN_RR_RATIO: float = 2.0

# วนลูปทุก 5 นาที
LOOP_INTERVAL_SECONDS: int = 300

# ── AI provider ──────────────────────────────────
# "anthropic" = Claude API (ต้องมี key), "ollama" = local model บนเครื่อง
AI_PROVIDER: str = os.getenv("AI_PROVIDER", "anthropic")

# Claude API key สำหรับ AI analysis
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# Ollama (local) endpoint
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# model id — default ต่างกันตาม provider
AI_MODEL: str = os.getenv(
    "AI_MODEL",
    "qwen2.5:7b" if AI_PROVIDER == "ollama" else "claude-opus-4-8",
)

# path ของ Obsidian vault สำหรับบันทึก journal
OBSIDIAN_VAULT_PATH: str = os.getenv(
    "OBSIDIAN_VAULT_PATH", "C:/ObsidianVault/Trading"
)

# SQLite database path
DB_PATH: str = os.getenv("DB_PATH", "trades.db")

# confidence ขั้นต่ำก่อนส่ง order
MIN_CONFIDENCE: int = 60

# จำนวน bars ที่ดึงมาวิเคราะห์
CANDLE_BARS: int = 200

# MetaApi retry settings
METAAPI_RETRY_DELAY: int = 5   # วินาที
METAAPI_MAX_RETRIES: int = 10

# WebSocket push interval (วินาที)
WS_PUSH_INTERVAL: int = 5

# คำนวณ AI progress ทุกกี่ cycle
AI_PROGRESS_CYCLE: int = 10
