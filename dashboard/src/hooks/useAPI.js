import { useState, useEffect, useCallback } from 'react'

const BASE = import.meta.env.VITE_API_URL || ''

// Mock data สำหรับแสดงเมื่อ backend offline
const MOCK = {
  '/api/status': {
    bot_running: false,
    account: { balance: 10000, equity: 9987.5, floating: -12.5, currency: 'USD', broker: 'Demo' },
    current_signal: {
      direction: 'BUY', confidence: 72, entry: 2348.50, sl: 2340.00, tp: 2366.00,
      rr: 2.06, fib_hit: 0.618, fvg: true, choch: true, bos: false,
      reason: '✅ CHoCH ตรวจพบแนวโน้ม BUY\n✅ Fib 0.618 golden zone\n✅ FVG ซ้อนทับ\n❌ BOS ยังไม่ยืนยัน',
    },
  },
  '/api/signals': [
    { id: 1, timestamp: new Date().toISOString(), direction: 'BUY', confidence: 72, entry: 2348.5, sl: 2340, tp: 2366, rr: 2.06, fib_hit: 0.618, fvg: true, choch: true, bos: false, executed: true },
    { id: 2, timestamp: new Date(Date.now() - 3e5).toISOString(), direction: 'SELL', confidence: 45, entry: 2355, sl: 2363, tp: 2339, rr: 2.0, fib_hit: 0.786, fvg: false, choch: false, bos: false, executed: false },
  ],
  '/api/orders': [
    { id: 1, timestamp: new Date().toISOString(), direction: 'BUY', lot: 0.01, entry: 2348.5, sl: 2340, tp: 2366, status: 'open', pnl: null },
    { id: 2, timestamp: new Date(Date.now() - 86400e3).toISOString(), direction: 'SELL', lot: 0.01, entry: 2362, sl: 2370, tp: 2346, status: 'closed', pnl: 16, close_price: 2346 },
  ],
  '/api/orders/stats': { total: 12, wins: 8, losses: 4, win_rate: 66.7, total_pnl: 124.5, best_trade: 32.1, worst_trade: -18.4 },
  '/api/equity-curve': Array.from({ length: 20 }, (_, i) => ({
    timestamp: new Date(Date.now() - (19 - i) * 3e5).toISOString(),
    equity: 9800 + Math.random() * 400,
    pnl: (Math.random() - 0.4) * 30,
  })),
  '/api/ai-progress': [
    { id: 1, timestamp: new Date().toISOString(), version: 3, win_rate: 66.7, total_trades: 12, total_pnl: 124.5, sharpe: 1.24, max_drawdown: 45.2 },
    { id: 2, timestamp: new Date(Date.now() - 86400e3).toISOString(), version: 2, win_rate: 60, total_trades: 10, total_pnl: 88, sharpe: 0.98, max_drawdown: 55 },
  ],
  '/api/daily-stats': [
    { date: new Date().toISOString().slice(0, 10), total_trades: 2, wins: 1, losses: 1, pnl: 14.5, drawdown: 18.4, stopped: false },
  ],
}

function getMockData(path) {
  const key = path.split('?')[0]
  return MOCK[key] ?? null
}

export function useAPI(path, { refreshMs = 0 } = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [offline, setOffline] = useState(false)

  const fetch_ = useCallback(async () => {
    try {
      const res = await fetch(`${BASE}${path}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setData(json)
      setOffline(false)
      setError(null)
    } catch (err) {
      // backend offline → ใช้ mock data
      const mock = getMockData(path)
      if (mock !== null) {
        setData(mock)
        setOffline(true)
        setError(null)
      } else {
        setError(err.message)
        setOffline(true)
      }
    } finally {
      setLoading(false)
    }
  }, [path])

  useEffect(() => {
    fetch_()
    if (refreshMs > 0) {
      const id = setInterval(fetch_, refreshMs)
      return () => clearInterval(id)
    }
  }, [fetch_, refreshMs])

  return { data, loading, error, offline, refetch: fetch_ }
}
