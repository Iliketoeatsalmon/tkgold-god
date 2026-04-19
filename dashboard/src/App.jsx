import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Signals from './pages/Signals'
import Orders from './pages/Orders'
import AIProgress from './pages/AIProgress'

const NAV = [
  { to: '/dashboard', label: 'Dashboard',   icon: '◈' },
  { to: '/signals',   label: 'Signals',     icon: '⟡' },
  { to: '/orders',    label: 'Orders',      icon: '▤' },
  { to: '/ai',        label: 'AI Progress', icon: '◉' },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="layout">
        <nav className="sidebar">
          <div className="sidebar-logo">⬡ XAUUSD SMC</div>
          {NAV.map(n => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              <span>{n.icon}</span>
              <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/signals" element={<Signals />} />
            <Route path="/orders" element={<Orders />} />
            <Route path="/ai" element={<AIProgress />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
