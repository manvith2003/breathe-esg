import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { login as apiLogin, getMe } from '../api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      getMe().then(r => { setUser(r.data); setLoading(false); })
             .catch(() => { localStorage.clear(); setLoading(false); });
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (username, password) => {
    const { data } = await apiLogin(username, password);
    localStorage.setItem('access_token', data.access);
    localStorage.setItem('refresh_token', data.refresh);
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(() => {
    localStorage.clear();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
