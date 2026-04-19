import { useState } from 'react'
import SMCChecklist from './SMCChecklist'
import FibVisualizer from './FibVisualizer'

function AIAnalysisButton({ signalId }) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState('')

  async function analyze() {
    setLoading(true)
    try {
      const res = await fetch('/api/ai-analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ signal_id: signalId }),
      })
      const data = await res.json()
      setResult(data.analysis || data.detail || 'ไม่มีผล')
    } catch (e) {
      setResult(`Error: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <button className="btn-gold" onClick={analyze} disabled={loading} style={{ marginTop: 8 }}>
        {loading ? 'กำลังวิเคราะห์...' : '⬡ AI Analysis'}
      </button>
      {result && (
        <div style={{
          marginTop: 12, padding: 12, background: 'var(--bg)',
          borderRadius: 8, fontSize: 12, color: 'var(--text2)',
          whiteSpace: 'pre-wrap', lineHeight: 1.8,
          border: '1px solid var(--border)',
        }}>
          {result}
        </div>
      )}
    </div>
  )
}

export default function SignalCard({ signal }) {
  const [expanded, setExpanded] = useState(false)
  const dir = signal.direction
  const conf = signal.confidence ?? 0
  const confColor = conf >= 70 ? 'var(--green)' : conf >= 50 ? 'var(--gold)' : 'var(--red)'

  return (
    <div className="card" style={{ cursor: 'pointer' }}>
      {/* Header row */}
      <div
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
        onClick={() => setExpanded(!expanded)}
      >
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span className={`badge badge-${dir?.toLowerCase()}`}>{dir}</span>
          <span className="mono" style={{ color: 'var(--text2)', fontSize: 12 }}>
            {new Date(signal.timestamp).toLocaleString('th', { dateStyle: 'short', timeStyle: 'short' })}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <div className="mono" style={{ color: confColor, fontWeight: 700 }}>{conf}%</div>
          <div style={{ fontSize: 12, color: 'var(--text2)' }}>
            {signal.entry} → {signal.tp}
          </div>
          <div style={{ color: 'var(--text2)', transform: expanded ? 'rotate(180deg)' : 'none', transition: '0.2s' }}>▾</div>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{ marginTop: 16, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
            <SMCChecklist signal={signal} />
            <div>
              <div className="text2" style={{ fontSize: 11, marginBottom: 8 }}>ENTRY DETAILS</div>
              {[
                ['Entry', signal.entry, 'var(--text)'],
                ['SL',    signal.sl,    'var(--red)'],
                ['TP',    signal.tp,    'var(--green)'],
                ['R:R',   signal.rr,    'var(--gold)'],
              ].map(([l, v, c]) => (
                <div key={l} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span className="text2" style={{ fontSize: 12 }}>{l}</span>
                  <span className="mono" style={{ color: c, fontSize: 13, fontWeight: 700 }}>{v ?? '—'}</span>
                </div>
              ))}
            </div>
          </div>

          {signal.reason && (
            <div style={{ marginBottom: 12, padding: 10, background: 'var(--bg3)', borderRadius: 6, fontSize: 12, color: 'var(--text2)', whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
              {signal.reason}
            </div>
          )}

          <FibVisualizer signal={signal} />
          <AIAnalysisButton signalId={signal.id} />
        </div>
      )}
    </div>
  )
}
