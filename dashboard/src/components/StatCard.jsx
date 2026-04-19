export default function StatCard({ label, value, sub, color, mono = true }) {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div className="text2" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        {label}
      </div>
      <div
        className={mono ? 'mono' : ''}
        style={{ fontSize: 24, fontWeight: 700, color: color || 'var(--text)' }}
      >
        {value}
      </div>
      {sub && <div className="text2" style={{ fontSize: 12 }}>{sub}</div>}
    </div>
  )
}
