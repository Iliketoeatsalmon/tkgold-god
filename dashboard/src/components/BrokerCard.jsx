import { useAPI } from '../hooks/useAPI'

export default function BrokerCard() {
  const { data, loading, offline } = useAPI('/api/status', { refreshMs: 10000 })
  const account = data?.account || {}
  const running = data?.bot_running

  const floating = account.floating ?? 0
  const floatColor = floating >= 0 ? 'var(--green)' : 'var(--red)'

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontWeight: 600 }}>Broker Account</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: running ? 'var(--green)' : 'var(--red)',
            boxShadow: running ? '0 0 6px var(--green)' : 'none',
          }} />
          {running ? 'Connected' : 'Offline'}
        </div>
      </div>

      {loading ? (
        <div className="text2">กำลังโหลด...</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div>
            <div className="text2" style={{ fontSize: 11 }}>BALANCE</div>
            <div className="mono" style={{ fontSize: 20, fontWeight: 700 }}>
              ${(account.balance || 0).toLocaleString('en', { minimumFractionDigits: 2 })}
            </div>
          </div>
          <div>
            <div className="text2" style={{ fontSize: 11 }}>EQUITY</div>
            <div className="mono" style={{ fontSize: 20, fontWeight: 700 }}>
              ${(account.equity || 0).toLocaleString('en', { minimumFractionDigits: 2 })}
            </div>
          </div>
          <div>
            <div className="text2" style={{ fontSize: 11 }}>FLOATING P&L</div>
            <div className="mono" style={{ fontSize: 18, fontWeight: 700, color: floatColor }}>
              {floating >= 0 ? '+' : ''}{floating.toFixed(2)}
            </div>
          </div>
          <div>
            <div className="text2" style={{ fontSize: 11 }}>BROKER</div>
            <div style={{ fontSize: 14, fontWeight: 500 }}>{account.broker || '—'}</div>
          </div>
        </div>
      )}

      {offline && (
        <div style={{ fontSize: 11, color: 'var(--text2)', fontStyle: 'italic' }}>
          * แสดง mock data (backend offline)
        </div>
      )}
    </div>
  )
}
