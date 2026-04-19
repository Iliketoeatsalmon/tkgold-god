import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { useAPI } from '../hooks/useAPI'

export default function AIProgressPanel() {
  const { data, loading } = useAPI('/api/ai-progress', { refreshMs: 60000 })
  const history = (data || []).slice().reverse() // เรียง version น้อย → มาก

  const latest = history.at(-1) || {}

  const winRateTrend = history.map(d => ({
    v:  `v${d.version}`,
    wr: d.win_rate,
  }))

  const sharpeData = history.map(d => ({
    v:      `v${d.version}`,
    sharpe: d.sharpe,
  }))

  if (loading) return <div className="text2">กำลังโหลด...</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Latest stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        {[
          { l: 'Win Rate',     v: `${latest.win_rate ?? 0}%`, c: latest.win_rate >= 50 ? 'var(--green)' : 'var(--red)' },
          { l: 'Total Trades', v: latest.total_trades ?? 0 },
          { l: 'Total PnL',    v: `$${latest.total_pnl?.toFixed(2) ?? 0}`, c: latest.total_pnl >= 0 ? 'var(--green)' : 'var(--red)' },
          { l: 'Sharpe',       v: latest.sharpe ?? 0, c: latest.sharpe >= 1 ? 'var(--green)' : 'var(--text2)' },
        ].map(({ l, v, c }) => (
          <div key={l} className="card" style={{ padding: 16 }}>
            <div className="text2" style={{ fontSize: 10, textTransform: 'uppercase', marginBottom: 4 }}>{l}</div>
            <div className="mono" style={{ fontSize: 22, fontWeight: 700, color: c || 'var(--text)' }}>{v}</div>
          </div>
        ))}
      </div>

      {/* Win Rate trend */}
      <div className="card">
        <div style={{ fontWeight: 600, marginBottom: 12 }}>Win Rate Trend</div>
        <ResponsiveContainer width="100%" height={120}>
          <LineChart data={winRateTrend}>
            <XAxis dataKey="v" tick={{ fill: '#555', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis domain={[0, 100]} tick={{ fill: '#555', fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `${v}%`} width={36} />
            <Tooltip
              contentStyle={{ background: '#0f0f0f', border: '1px solid #232323', borderRadius: 8 }}
              formatter={v => [`${v}%`, 'Win Rate']}
            />
            <Line type="monotone" dataKey="wr" stroke="var(--gold)" strokeWidth={2} dot={{ fill: 'var(--gold)', r: 4 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Sharpe bar chart */}
      <div className="card">
        <div style={{ fontWeight: 600, marginBottom: 12 }}>Sharpe Ratio per Version</div>
        <ResponsiveContainer width="100%" height={100}>
          <BarChart data={sharpeData}>
            <XAxis dataKey="v" tick={{ fill: '#555', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#555', fontSize: 11 }} axisLine={false} tickLine={false} width={30} />
            <Tooltip
              contentStyle={{ background: '#0f0f0f', border: '1px solid #232323', borderRadius: 8 }}
              formatter={v => [v, 'Sharpe']}
            />
            <Bar dataKey="sharpe" radius={[4, 4, 0, 0]}>
              {sharpeData.map((entry, i) => (
                <Cell key={i} fill={entry.sharpe >= 1 ? 'var(--green)' : entry.sharpe >= 0 ? 'var(--gold)' : 'var(--red)'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Version history table */}
      <div className="card">
        <div style={{ fontWeight: 600, marginBottom: 12 }}>Version History</div>
        <table>
          <thead>
            <tr>
              <th>Version</th>
              <th>Win Rate</th>
              <th>Trades</th>
              <th>PnL</th>
              <th>Sharpe</th>
              <th>Max DD</th>
            </tr>
          </thead>
          <tbody>
            {history.slice().reverse().map(d => (
              <tr key={d.id}>
                <td className="mono gold">v{d.version}</td>
                <td className="mono" style={{ color: d.win_rate >= 50 ? 'var(--green)' : 'var(--red)' }}>
                  {d.win_rate}%
                </td>
                <td className="mono">{d.total_trades}</td>
                <td className="mono" style={{ color: d.total_pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                  {d.total_pnl >= 0 ? '+' : ''}{d.total_pnl?.toFixed(2)}
                </td>
                <td className="mono">{d.sharpe}</td>
                <td className="mono red">{d.max_drawdown?.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
