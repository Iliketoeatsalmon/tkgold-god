# XAUUSD SMC AI Trading System

ระบบเทรด XAUUSD อัตโนมัติบน Windows โดยใช้ SMC (Smart Money Concepts) + Fibonacci + Claude AI

## โครงสร้างระบบ

```
tkgold-god/
├── config.py          — การตั้งค่าทั้งหมด
├── db.py              — SQLite database
├── strategy.py        — SMC Strategy Engine
├── risk.py            — Risk Management
├── bot.py             — Trading Bot หลัก
├── server.py          — FastAPI Backend
├── obsidian_writer.py — Obsidian Journal Writer
├── requirements.txt
├── .env.example
└── dashboard/         — React Frontend
    ├── src/
    │   ├── pages/     — Dashboard, Signals, Orders, AIProgress
    │   ├── components/
    │   └── hooks/     — useAPI, useWebSocket
    └── package.json
```

## ขั้นตอนติดตั้งบน Windows

### 1. ติดตั้ง Python dependencies
```cmd
pip install -r requirements.txt
```

### 2. ตั้งค่า environment variables
```cmd
copy .env.example .env
```
เปิดไฟล์ `.env` แล้วใส่ค่า:
- `METAAPI_TOKEN` — Token จาก [metaapi.cloud](https://metaapi.cloud)
- `ACCOUNT_ID` — Account ID ของ MT5 ใน MetaApi
- `ANTHROPIC_API_KEY` — API Key จาก [console.anthropic.com](https://console.anthropic.com)
- `OBSIDIAN_VAULT_PATH` — path ของ Obsidian vault เช่น `C:\ObsidianVault\Trading`

### 3. รัน Trading Bot (Terminal 1)
```cmd
python bot.py
```

### 4. รัน API Server (Terminal 2)
```cmd
uvicorn server:app --reload --port 8000
```

### 5. รัน Dashboard (Terminal 3)
```cmd
cd dashboard
npm install
npm run dev
```

### 6. เปิด Browser
```
http://localhost:5173
```

---

## การทำงานของระบบ

### Strategy Logic
1. ดึง H1, M15, M5 candles จาก MetaApi ทุก 5 นาที
2. ตรวจหา **Swing High/Low** ด้วย ZigZag lookback
3. วาด **Fibonacci** จาก swing pair ล่าสุด
4. ตรวจ **FVG** (Fair Value Gap) บน M15
5. ตรวจ **CHoCH** และ **BOS** บน H1
6. ให้ **Confidence Score** (max 100):
   - Fib golden zone hit: +30
   - FVG confluence: +30
   - CHoCH confirm: +25
   - BOS break: +15
7. ส่ง order เมื่อ confidence ≥ 60 และผ่าน risk check

### Risk Management
- **Daily Loss Limit**: หยุดเมื่อขาดทุนเกิน 3% ของ balance
- **One Position**: ไม่เปิด XAUUSD ซ้อน
- **R:R Filter**: ต้องได้ RR ≥ 2.0 ถึงจะเปิด
- **Lot Sizing**: คำนวณ lot ตาม % risk และ SL distance

### Obsidian Journal
- `trades/YYYY-MM-DD_XAUUSD_BUY.md` — journal ทุก trade
- `daily/YYYY-MM-DD.md` — สรุปรายวัน
- `strategy/performance.md` — tracking AI progress

---

## Dashboard Features
- **Dark theme** — #070707 background, gold accent
- **Live Signal** — อัปเดตผ่าน WebSocket ทุก 5 วินาที
- **Fibonacci Visualizer** — แสดง levels + FVG zone แบบ visual
- **SMC Checklist** — tick/cross ทุก condition
- **Equity Curve** — area chart เรียลไทม์
- **Orders Table** — กรอง open/closed, sort
- **AI Progress** — version history, win rate trend, Sharpe bar chart
- **Mock Data** — แสดงข้อมูลตัวอย่างเมื่อ backend offline

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | สถานะ bot + account |
| GET | `/api/signals` | Signal history |
| GET | `/api/signals/live` | Signal ล่าสุด |
| GET | `/api/orders` | Order history |
| GET | `/api/orders/stats` | Win rate, PnL stats |
| GET | `/api/equity-curve` | Equity curve data |
| GET | `/api/ai-progress` | AI version history |
| GET | `/api/daily-stats` | Daily stats |
| POST | `/api/ai-analysis` | Claude AI analysis |
| WS | `/ws/live` | Live push updates |

---

## หมายเหตุ
- ต้องมี MetaApi account และ MT5 account เชื่อมแล้ว
- Dashboard แสดง mock data อัตโนมัติเมื่อ backend ไม่ตอบสนอง
- Bot restart อัตโนมัติถ้า MetaApi disconnect (retry 10 ครั้ง)
- ใช้ SQLite ไม่ต้องติดตั้ง database แยก
