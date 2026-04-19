import { useAPI } from '../hooks/useAPI'
import { useWebSocket } from '../hooks/useWebSocket'
import BrokerCard from '../components/BrokerCard'
import LiveSignal from '../components/LiveSignal'
import EquityCurve from '../components/EquityCurve'
import StatCard from '../components/StatCard'
import OrdersTable from '../components/OrdersTable'

export default function Dashboard() {
  const { data: stats, offline } = useAPI('/api/orders/stats', { refreshMs: 15000 })
  const { data: daily } = useAPI('/api/daily-stats', { refreshMs: 30000 })
  const { connected } = useWebSocket('/ws/live')
  const today = daily?.[0] || {}

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 className="page-title" style={{ margin: 0 }}>Dashboard</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text2)' }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: connected ? 'var(--green)' : 'var(--red)',
          }} />
          {connected ? 'Live' : 'Offline'}
        </div>
      </div>

      {offline && (
        <div className="offline-banner">
          ⚠ Backend offline — แสดง mock data
        </div>
      )}

      {/* Summary stats row */}
      <div className="grid-4" style={{ marginBottom: 16 }}>
        <StatCard
          label="Win Rate"
          value={`${stats?.win_rate ?? 0}%`}
          sub={`${stats?.wins ?? 0}W / ${stats?.losses ?? 0}L`}
          color={stats?.win_rate >= 50 ? 'var(--green)' : 'var(--red)'}
        />
        <StatCard
          label="Total PnL"
          value={`$${stats?.total_pnl?.toFixed(2) ?? '0.00'}`}
          color={stats?.total_pnl >= 0 ? 'var(--green)' : 'var(--red)'}
        />
        <StatCard
          label="Today PnL"
          value={`$${today.pnl?.toFixed(2) ?? '0.00'}`}
          sub={`${today.total_trades ?? 0} trades วันนี้`}
          color={today.pnl >= 0 ? 'var(--green)' : 'var(--red)'}
        />
        <StatCard
          label="Best Trade"
          value={`$${stats?.best_trade?.toFixed(2) ?? '0.00'}`}
          sub={`Worst: $${stats?.worst_trade?.toFixed(2) ?? '0.00'}`}
          color="var(--gold)"
        />
      </div>

      {/* Main area */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <BrokerCard />
        <EquityCurve />
      </div>

      {/* Live Signal */}
      <div style={{ marginBottom: 16 }}>
        <LiveSignal />
      </div>

      {/* Recent orders */}
      <div className="card">
        <div style={{ fontWeight: 600, marginBottom: 12 }}>Recent Orders</div>
        <OrdersTable limit={10} />
      </div>
    </div>
  )
}
