import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const NAV_ITEMS = [
  { path: '/dashboard', icon: '📊', label: 'Dashboard' },
  { path: '/ingest', icon: '📥', label: 'Ingest Data' },
  { path: '/review', icon: '🔍', label: 'Review Queue' },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const profile = user?.profile;
  const orgName = profile?.organization?.name || 'Organization';
  const role = profile?.role || 'USER';
  const initials = `${user?.first_name?.[0] || ''}${user?.last_name?.[0] || user?.username?.[0] || ''}`.toUpperCase();

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">🌿</div>
          <div>
            <div className="sidebar-logo-text">BreatheESG</div>
            <div className="sidebar-logo-sub">Emissions Intelligence</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <span className="sidebar-section-label">Navigation</span>
          {NAV_ITEMS.map(item => (
            <button
              key={item.path}
              className={`nav-link ${location.pathname === item.path ? 'active' : ''}`}
              onClick={() => navigate(item.path)}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </button>
          ))}

          <span className="sidebar-section-label" style={{ marginTop: 24 }}>Reference</span>
          <button className="nav-link" onClick={() => window.open('/admin/', '_blank')}>
            <span className="nav-icon">⚙️</span>
            Admin Panel
          </button>
        </nav>

        <div className="sidebar-footer">
          <div className="user-pill">
            <div className="user-avatar">{initials || '?'}</div>
            <div className="user-info">
              <div className="user-name">{user?.first_name || user?.username}</div>
              <div className="user-role">{role} · {orgName.split(' ')[0]}</div>
            </div>
            <button className="logout-btn" onClick={logout} title="Sign out">⇥</button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="main-content">
        <div className="page-content">
          {children}
        </div>
      </main>
    </div>
  );
}
