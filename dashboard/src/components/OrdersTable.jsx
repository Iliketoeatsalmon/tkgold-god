import { useState } from 'react'
import { useAPI } from '../hooks/useAPI'

export default function OrdersTable({ limit = 20 }) {
  const [statusFilter, setStatusFilter] = useState('all')
  const { data, loading } = useAPI(
    `/api/orders?limit=${limit}&status=${statusFilter}`,
    { refreshMs: 10000 }
  )

  const orders = data || []

  return (
    <div>
      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        {['all', 'open', 'closed'].map(s => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={statusFilter === s ? 'btn-gold' : 'btn-ghost'}
            style={{ padding: '5px 14px', fontSize: 12 }}
          >
            {s}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text2">กำลังโหลด...</div>
      ) : orders.length === 0 ? (
        <div className="text2" style={{ padding: 16 }}>ไม่มี orders</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>วันที่</th>
              <th>Direction</th>
              <th>Entry</th>
              <th>SL</th>
              <th>TP</th>
              <th>Close</th>
              <th>Lot</th>
              <th>P&L</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {orders.map(o => {
              const pnl = o.pnl
              const pnlColor = pnl > 0 ? 'var(--green)' : pnl < 0 ? 'var(--red)' : 'var(--text2)'
              return (
                <tr key={o.id}>
                  <td className="mono text2">{o.id}</td>
                  <td style={{ fontSize: 12 }}>
                    {new Date(o.timestamp).toLocaleDateString('th', { day: '2-digit', month: 'short' })}
                    {' '}
                    <span className="text2">
                      {new Date(o.timestamp).toLocaleTimeString('th', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </td>
                  <td>
                    <span className={`badge badge-${(o.direction || '').toLowerCase()}`}>
                      {o.direction}
                    </span>
                  </td>
                  <td className="mono">{o.entry}</td>
                  <td className="mono red">{o.sl}</td>
                  <td className="mono green">{o.tp}</td>
                  <td className="mono">{o.close_price ?? '—'}</td>
                  <td className="mono">{o.lot}</td>
                  <td className="mono" style={{ color: pnlColor, fontWeight: 700 }}>
                    {pnl != null ? `${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}` : '—'}
                  </td>
                  <td>
                    <span className={`badge badge-${o.status}`}>{o.status}</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
