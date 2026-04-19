import { useWebSocket } from '../hooks/useWebSocket'
import { useAPI } from '../hooks/useAPI'
import SMCChecklist from './SMCChecklist'
import FibVisualizer from './FibVisualizer'

function ConfidenceGauge({ value = 0 }) {
  const r = 40
  const circ = 2 * Math.PI * r
  const dash = circ * (value / 100)
  const color = value >= 70 ? 'var(--green)' : value >= 50 ? 'var(--gold)' : 'var(--red)'

  return (
    <div style={{ position: 'relative', width: 100, height: 100 }}>
      <svg width="100" height="100" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={r} fill="none" stroke="var(--border)" strokeWidth="8" />
        <circle
          cx="50" cy="50" r={r}
          fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
          style={{ transition: 'stroke-dasharray 0.5s ease' }}
        />
      </svg>
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
      }}>
        <div className="mono" style={{ fontSize: 20, fontWeight: 700, color }}>{value}</div>
        <div style={{ fontSize: 9, color: 'var(--text2)' }}>CONF</div>
      </div>
    </div>
  )
}

export default function LiveSignal() {
  const { message } = useWebSocket('/ws/live')
  const { data: statusData } = useAPI('/api/status', { refreshMs: 5000 })

  const signal = message?.signal || statusData?.current_signal || {}
  const dir = signal.direction

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ fontWeight: 600 }}>Live Signal</div>
        {dir && (
          <span className={`badge badge-${dir.toLowerCase()}`}>{dir}</span>
        )}
      </div>

      {!dir ? (
        <div className="text2" style={{ fontSize: 13 }}>รอ signal...</div>
      ) : (
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          {/* Gauge */}
          <ConfidenceGauge value={signal.confidence ?? 0} />

          {/* Entry info */}
          <div style={{ flex: 1, minWidth: 180 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 16 }}>
              {[
                { l: 'Entry', v: signal.entry },
                { l: 'SL',    v: signal.sl, color: 'var(--red)' },
                { l: 'TP',    v: signal.tp, color: 'var(--green)' },
              ].map(({ l, v, color }) => (
                <div key={l}>
                  <div className="text2" style={{ fontSize: 10 }}>{l}</div>
                  <div className="mono" style={{ fontSize: 16, fontWeight: 700, color: color || 'var(--text)' }}>
                    {v ?? '—'}
                  </div>
                </div>
              ))}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text2)' }}>
              R:R <span className="mono gold" style={{ fontWeight: 700 }}>{signal.rr ?? '—'}</span>
            </div>
          </div>

          {/* Checklist */}
          <SMCChecklist signal={signal} />
        </div>
      )}

      {signal.reason && (
        <div style={{
          marginTop: 16, padding: 12, background: 'var(--bg3)',
          borderRadius: 8, fontSize: 12, color: 'var(--text2)',
          whiteSpace: 'pre-wrap', lineHeight: 1.8,
        }}>
          {signal.reason}
        </div>
      )}

      {dir && <div style={{ marginTop: 16 }}><FibVisualizer signal={signal} /></div>}
    </div>
  )
}
