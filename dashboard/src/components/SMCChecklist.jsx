export default function SMCChecklist({ signal = {} }) {
  const items = [
    { key: 'fib_hit', label: `Fib ${signal.fib_hit ?? '—'} Hit` },
    { key: 'fvg',     label: 'FVG Confluence' },
    { key: 'choch',   label: 'CHoCH Confirm' },
    { key: 'bos',     label: 'BOS Break' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ fontSize: 12, color: 'var(--text2)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 4 }}>
        SMC Checklist
      </div>
      {items.map(item => {
        const ok = !!signal[item.key]
        return (
          <div key={item.key} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 22, height: 22, borderRadius: 6,
              background: ok ? 'rgba(0,217,126,0.15)' : 'rgba(255,92,92,0.1)',
              border: `1px solid ${ok ? 'var(--green)' : 'rgba(255,92,92,0.3)'}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 13, flexShrink: 0,
            }}>
              {ok ? '✓' : '✗'}
            </div>
            <span style={{ fontSize: 13, color: ok ? 'var(--text)' : 'var(--text2)' }}>
              {item.label}
            </span>
          </div>
        )
      })}
    </div>
  )
}
