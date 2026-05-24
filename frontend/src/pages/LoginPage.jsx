import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

export default function LoginPage() {
  const [form, setForm] = useState({ username: '', password: '' });
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const handle = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(form.username, form.password);
      navigate('/dashboard');
    } catch {
      toast({ type: 'error', title: 'Login failed', message: 'Invalid username or password.' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* Background orbs */}
      <div className="login-bg-orb" style={{
        width: 500, height: 500,
        background: 'var(--color-primary)',
        top: -100, left: -100,
      }} />
      <div className="login-bg-orb" style={{
        width: 400, height: 400,
        background: 'var(--color-scope3)',
        bottom: -100, right: -100,
      }} />

      <div className="login-card">
        <div className="login-logo">
          <div className="login-logo-icon">🌿</div>
          <div>
            <div className="login-title">BreatheESG</div>
            <div className="login-subtitle">Emissions Data Platform</div>
          </div>
        </div>

        <form onSubmit={handle}>
          <div className="form-group">
            <label className="form-label">Username</label>
            <input
              id="username"
              className="input"
              placeholder="Enter username"
              value={form.username}
              onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
              autoComplete="username"
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              id="password"
              type="password"
              className="input"
              placeholder="Enter password"
              value={form.password}
              onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
              autoComplete="current-password"
              required
            />
          </div>
          <button id="login-submit" type="submit" className="login-btn" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign in →'}
          </button>
        </form>

        <div className="login-demo-creds">
          <div style={{ fontWeight: 600, marginBottom: 6, color: 'var(--text-primary)' }}>
            Demo credentials
          </div>
          <div>Admin: <code>admin</code> / <code>breatheesg2024</code></div>
          <div style={{ marginTop: 4 }}>Analyst: <code>analyst</code> / <code>breatheesg2024</code></div>
        </div>
      </div>
    </div>
  );
}
