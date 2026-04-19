import { useAPI } from '../hooks/useAPI'
import StatCard from '../components/StatCard'
import OrdersTable from '../components/OrdersTable'

export default function Orders() {
  const { data: stats } = useAPI('/api/orders/stats', { refreshMs: 30000 })

  return (
    <div>
      <h1 className="page-title">Orders</h1>

      <div className="grid-4" style={{ marginBottom: 20 }}>
        <StatCard label="Total Trades" value={stats?.total ?? 0} mono />
        <StatCard
          label="Win Rate"
          value={`${stats?.win_rate ?? 0}%`}
          color={stats?.win_rate >= 50 ? 'var(--green)' : 'var(--red)'}
        />
        <StatCard
          label="Total PnL"
          value={`$${stats?.total_pnl?.toFixed(2) ?? '0.00'}`}
          color={stats?.total_pnl >= 0 ? 'var(--green)' : 'var(--red)'}
        />
        <StatCard
          label="Best Trade"
          value={`$${stats?.best_trade?.toFixed(2) ?? '0.00'}`}
          sub={`Worst: $${stats?.worst_trade?.toFixed(2) ?? '0.00'}`}
          color="var(--gold)"
        />
      </div>

      <div className="card">
        <OrdersTable limit={50} />
      </div>
    </div>
  )
}
