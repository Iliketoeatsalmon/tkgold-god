#!/usr/bin/env bash
#
# run.sh — เปิดทุก service ของ XAUUSD SMC AI Trading ในคำสั่งเดียว
# ใช้: ./run.sh           รันครบ (ollama + bot + server + dashboard)
#      ./run.sh --no-bot  ข้าม bot (กรณีไม่มี MetaApi token)
#
set -euo pipefail
cd "$(dirname "$0")"

NO_BOT=0
[[ "${1:-}" == "--no-bot" ]] && NO_BOT=1

# เก็บ PID ของทุก process ที่เปิด เพื่อปิดให้หมดตอน Ctrl+C
PIDS=()
cleanup() {
  echo ""
  echo "🛑 ปิด service ทั้งหมด..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  exit 0
}
trap cleanup INT TERM

# ── 0. โหลด .env ─────────────────────────────────
if [[ ! -f .env ]]; then
  echo "❌ ไม่พบ .env — รัน: cp .env.example .env แล้วใส่ค่าก่อน"
  exit 1
fi

# ── 1. Ollama ────────────────────────────────────
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "▶️  เริ่ม Ollama..."
  ollama serve > /tmp/ollama.log 2>&1 &
  PIDS+=($!)
  # รอ daemon พร้อม
  for _ in $(seq 1 20); do
    curl -s http://localhost:11434/api/tags >/dev/null 2>&1 && break
    sleep 0.5
  done
else
  echo "✅ Ollama รันอยู่แล้ว"
fi

# ── 2. Trading bot ───────────────────────────────
if [[ "$NO_BOT" -eq 0 ]]; then
  echo "▶️  เริ่ม Trading bot..."
  python3 bot.py > bot.log 2>&1 &
  PIDS+=($!)
else
  echo "⏭️  ข้าม bot (--no-bot)"
fi

# ── 3. API server ────────────────────────────────
echo "▶️  เริ่ม API server (:8000)..."
uvicorn server:app --port 8000 > server.log 2>&1 &
PIDS+=($!)

# ── 4. Dashboard ─────────────────────────────────
echo "▶️  เริ่ม Dashboard (:5173)..."
( cd dashboard && [[ -d node_modules ]] || npm install ; npm run dev ) > dashboard.log 2>&1 &
PIDS+=($!)

echo ""
echo "════════════════════════════════════════"
echo "  Dashboard : http://localhost:5173"
echo "  API       : http://localhost:8000"
echo "  Logs      : bot.log / server.log / dashboard.log"
echo "  หยุดทั้งหมด: Ctrl+C"
echo "════════════════════════════════════════"

# รอจน Ctrl+C
wait
