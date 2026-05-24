import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import IngestionPage from './pages/IngestionPage';
import ReviewPage from './pages/ReviewPage';
import './index.css';

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return (
    <div className="loading-state" style={{ minHeight: '100vh' }}>
      <div className="spinner spinner-lg" />
      <span>Loading BreatheESG...</span>
    </div>
  );
  return user ? children : <Navigate to="/login" replace />;
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/*" element={
              <PrivateRoute>
                <Layout>
                  <Routes>
                    <Route path="/" element={<Navigate to="/dashboard" replace />} />
                    <Route path="/dashboard" element={<DashboardPage />} />
                    <Route path="/ingest" element={<IngestionPage />} />
                    <Route path="/review" element={<ReviewPage />} />
                  </Routes>
                </Layout>
              </PrivateRoute>
            } />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
