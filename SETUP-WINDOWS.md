# Setup บน Windows (MT5 direct — ฟรี)

## 1. ติดตั้งโปรแกรม

1. **Python 3.11+** — https://python.org/downloads (ติ๊ก "Add to PATH" ตอน install)
2. **MetaTrader 5 terminal** — โหลดจากเว็บ broker (เช่น Exness, IC Markets)
3. **Git** — https://git-scm.com

## 2. เปิดบัญชี demo + login MT5

1. สมัคร demo account กับ broker (ฟรี ได้ login/password/server มา)
2. เปิด MT5 terminal → File → Login to Trade Account → ใส่ credentials
3. เช็คชื่อ symbol ทอง ใน Market Watch — `XAUUSD` หรือ `XAUUSDm` หรือ `GOLD`
   (ถ้าไม่เจอ: คลิกขวา Market Watch → Show All)
4. **Tools → Options → Expert Advisors → ติ๊ก "Allow algorithmic trading"**
5. MT5 terminal **ต้องเปิดค้างไว้ตลอด** ที่ bot ทำงาน

## 3. Clone + ติดตั้ง dependencies

```bat
git clone <repo-url> tkgold-god
cd tkgold-god
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 4. ตั้งค่า .env

Copy `.env.example` → `.env` แล้วแก้:

```env
BROKER_BACKEND=mt5

# เว้นว่างได้ถ้า MT5 terminal login ค้างไว้แล้ว (แนะนำ)
MT5_LOGIN=
MT5_PASSWORD=
MT5_SERVER=

# ใส่ชื่อ symbol ตามที่เห็นใน Market Watch
SYMBOL=XAUUSD
```

## 5. รัน

เปิด 2 terminal (ทั้งคู่ activate venv ก่อน):

```bat
:: Terminal 1 — API server (dashboard backend)
python server.py

:: Terminal 2 — trading bot
python bot.py
```

Dashboard frontend:

```bat
cd dashboard
npm install
npm run dev -- --host
```

## 6. ดูจาก Mac

หา IP เครื่อง Windows: `ipconfig` → IPv4 Address (เช่น 192.168.1.50)

- Dashboard: `http://192.168.1.50:5173`
- API: `http://192.168.1.50:8000/api/status`

ถ้าเข้าไม่ได้ → Windows Firewall → allow port 5173 + 8000 (Private network)

## Troubleshooting

| อาการ | แก้ |
|---|---|
| `mt5.initialize ล้มเหลว` | MT5 terminal ยังไม่เปิด / ยังไม่ login |
| `ไม่พบ symbol XAUUSD` | เช็คชื่อจริงใน Market Watch แล้วแก้ `SYMBOL` ใน .env |
| `order_send ล้มเหลว retcode=10027` | ยังไม่เปิด "Allow algorithmic trading" (ข้อ 2.4) |
| Mac เข้า dashboard ไม่ได้ | firewall / เช็คว่า `npm run dev -- --host` มี `--host` |
