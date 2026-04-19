import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { useAPI } from '../hooks/useAPI'

const fmt = (v) => `$${v?.toFixed(2) ?? 0}`

export default function EquityCurve() {
  const { data, loading } = useAPI('/api/equity-curve', { refreshMs: 30000 })

  const chartData = (data || []).map(d => ({
    time:   new Date(d.timestamp).toLocaleTimeString('th', { hour: '2-digit', minute: '2-digit' }),
    equity: parseFloat(d.equity?.toFixed(2) ?? 0),
  }))

  const min = Math.min(...chartData.map(d => d.equity))
  const max = Math.max(...chartData.map(d => d.equity))
  const trend = chartData.length >= 2
    ? chartData.at(-1).equity - chartData[0].equity
    : 0
  const trendColor = trend >= 0 ? 'var(--green)' : 'var(--red)'

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ fontWeight: 600 }}>Equity Curve</div>
        <div className="mono" style={{ color: trendColor, fontSize: 14, fontWeight: 700 }}>
          {trend >= 0 ? '+' : ''}{trend.toFixed(2)}
        </div>
      </div>
      {loading ? (
        <div className="text2">กำลังโหลด...</div>
      ) : (
        <ResponsiveContainer width="100%" height={160}>
          <AreaChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor={trend >= 0 ? '#00d97e' : '#ff5c5c'} stopOpacity={0.3} />
                <stop offset="95%" stopColor={trend >= 0 ? '#00d97e' : '#ff5c5c'} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="time" tick={{ fill: '#555', fontSize: 10 }} tickLine={false} axisLine={false} />
            <YAxis domain={[min * 0.999, max * 1.001]} tick={{ fill: '#555', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={fmt} width={60} />
            <Tooltip
              contentStyle={{ background: '#0f0f0f', border: '1px solid #232323', borderRadius: 8 }}
              labelStyle={{ color: '#888', fontSize: 11 }}
              itemStyle={{ color: trendColor, fontFamily: 'var(--font-num)' }}
              formatter={(v) => [fmt(v), 'Equity']}
            />
            <Area
              type="monotone" dataKey="equity"
              stroke={trend >= 0 ? '#00d97e' : '#ff5c5c'}
              fill="url(#eqGrad)" strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
