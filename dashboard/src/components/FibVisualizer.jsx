const FIB_LEVELS = [0, 0.1, 0.14, 0.52, 0.57, 0.618, 0.786, 1]
const ENTRY_ZONE = [0.618, 0.786]

const FIB_COLORS = {
  0:     '#888',
  0.1:   '#c8a96e',
  0.14:  '#c8a96e',
  0.52:  '#4a8fff',
  0.57:  '#4a8fff',
  0.618: '#00d97e',
  0.786: '#00d97e',
  1:     '#888',
}

export default function FibVisualizer({ signal = {} }) {
  const { entry, sl, tp, direction, fib_hit, fvg } = signal

  if (!entry || !sl || !tp) {
    return <div className="text2" style={{ fontSize: 12 }}>ไม่มีข้อมูล Fib</div>
  }

  // คำนวณ price range ของ chart
  const allPrices = [entry, sl, tp].filter(Boolean)
  const minP = Math.min(...allPrices) * 0.999
  const maxP = Math.max(...allPrices) * 1.001
  const range = maxP - minP

  const toY = (price) => ((maxP - price) / range) * 100

  // คำนวณ Fibonacci prices (simplified visual)
  const swing_low = direction === 'BUY' ? sl : tp
  const swing_high = direction === 'BUY' ? tp : sl
  const diff = swing_high - swing_low

  const fibPrices = FIB_LEVELS.reduce((acc, lv) => {
    acc[lv] = direction === 'BUY'
      ? swing_high - diff * lv
      : swing_low + diff * lv
    return acc
  }, {})

  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        Fibonacci Levels
      </div>
      <div style={{ position: 'relative', height: 180, background: 'var(--bg3)', borderRadius: 8, overflow: 'hidden', padding: '0 60px 0 0' }}>
        <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0 }}>

          {/* Entry zone highlight (0.618 - 0.786) */}
          {(() => {
            const y1 = toY(Math.max(fibPrices[0.618] || 0, fibPrices[0.786] || 0))
            const y2 = toY(Math.min(fibPrices[0.618] || 0, fibPrices[0.786] || 0))
            return (
              <rect
                x="0" y={`${y1}%`}
                width="100%" height={`${y2 - y1}%`}
                fill="rgba(0,217,126,0.06)"
              />
            )
          })()}

          {/* FVG zone */}
          {fvg && (() => {
            const mid = (fibPrices[0.618] + fibPrices[0.786]) / 2
            const y = toY(mid)
            return (
              <rect
                x="0" y={`${y - 1.5}%`}
                width="80%" height="3%"
                fill="rgba(200,169,110,0.12)"
                stroke="rgba(200,169,110,0.3)"
                strokeWidth="1"
                strokeDasharray="4 2"
              />
            )
          })()}

          {/* Fib level lines */}
          {FIB_LEVELS.map(lv => {
            const price = fibPrices[lv]
            if (!price) return null
            const y = toY(price)
            const isHit = fib_hit == lv
            const color = FIB_COLORS[lv] || '#555'
            return (
              <line
                key={lv}
                x1="0" y1={`${y}%`}
                x2="100%" y2={`${y}%`}
                stroke={color}
                strokeWidth={isHit ? 2 : 1}
                strokeOpacity={isHit ? 1 : 0.4}
                strokeDasharray={isHit ? 'none' : '4 2'}
              />
            )
          })}

          {/* Entry marker */}
          {(() => {
            const y = toY(entry)
            return (
              <>
                <line x1="0" y1={`${y}%`} x2="100%" y2={`${y}%`}
                  stroke="var(--gold)" strokeWidth="2" />
                <circle cx="50%" cy={`${y}%`} r="5"
                  fill="var(--gold)" />
              </>
            )
          })()}
        </svg>

        {/* Labels */}
        <div style={{ position: 'absolute', right: 4, top: 0, bottom: 0, width: 56 }}>
          {FIB_LEVELS.map(lv => {
            const price = fibPrices[lv]
            if (!price) return null
            const y = toY(price)
            return (
              <div key={lv} style={{
                position: 'absolute',
                top: `${y}%`,
                transform: 'translateY(-50%)',
                fontSize: 9,
                color: FIB_COLORS[lv],
                fontFamily: 'var(--font-num)',
                opacity: fib_hit == lv ? 1 : 0.6,
              }}>
                {lv}
              </div>
            )
          })}
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 11, color: 'var(--text2)' }}>
        <span><span style={{ color: 'var(--gold)' }}>─</span> Entry</span>
        <span><span style={{ color: 'var(--green)' }}>░</span> Golden Zone</span>
        {fvg && <span><span style={{ color: 'var(--gold)', opacity: 0.6 }}>░</span> FVG</span>}
      </div>
    </div>
  )
}
