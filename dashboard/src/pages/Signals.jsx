import { useState } from 'react'
import { useAPI } from '../hooks/useAPI'
import SignalCard from '../components/SignalCard'

export default function Signals() {
  const [dirFilter, setDirFilter] = useState('all')
  const { data, loading, refetch } = useAPI('/api/signals?limit=50', { refreshMs: 30000 })

  const signals = (data || []).filter(s => {
    if (dirFilter === 'all') return true
    return s.direction === dirFilter
  })

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 className="page-title" style={{ margin: 0 }}>Signal History</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          {['all', 'BUY', 'SELL'].map(f => (
            <button
              key={f}
              onClick={() => setDirFilter(f)}
              className={dirFilter === f ? 'btn-gold' : 'btn-ghost'}
              style={{ padding: '5px 14px', fontSize: 12 }}
            >
              {f}
            </button>
          ))}
          <button className="btn-ghost" onClick={refetch} style={{ padding: '5px 14px', fontSize: 12 }}>
            ↻ Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text2">กำลังโหลด...</div>
      ) : signals.length === 0 ? (
        <div className="text2" style={{ padding: 24 }}>ไม่มี signals</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {signals.map(s => <SignalCard key={s.id} signal={s} />)}
        </div>
      )}
    </div>
  )
}
