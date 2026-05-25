import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: { 'Content-Type': 'application/json' },
});


// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-refresh on 401
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config;
    if (err.response?.status === 401 && !original._retry) {
      original._retry = true;
      const refresh = localStorage.getItem('refresh_token');
      if (refresh) {
        try {
          const { data } = await axios.post('/api/auth/refresh/', { refresh });
          localStorage.setItem('access_token', data.access);
          original.headers.Authorization = `Bearer ${data.access}`;
          return api(original);
        } catch {
          localStorage.clear();
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(err);
  }
);

export default api;

// ── Auth ──────────────────────────────────────────────────────────────────────
export const login = (username, password) =>
  api.post('/auth/login/', { username, password });

export const getMe = () => api.get('/auth/me/');

// ── Ingestion ─────────────────────────────────────────────────────────────────
export const uploadFile = (file, sourceType) => {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('source_type', sourceType);
  return api.post('/ingestion/upload/', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const getBatches = (params) => api.get('/ingestion/batches/', { params });
export const getBatch = (id) => api.get(`/ingestion/batches/${id}/`);

// ── Emissions ─────────────────────────────────────────────────────────────────
export const getEmissions = (params) => api.get('/emissions/', { params });
export const getEmission = (id) => api.get(`/emissions/${id}/`);
export const updateEmission = (id, data) => api.patch(`/emissions/${id}/`, data);

// ── Dashboard ─────────────────────────────────────────────────────────────────
export const getDashboardSummary = () => api.get('/dashboard/summary/');
export const getDashboardTimeline = () => api.get('/dashboard/timeline/');

// ── Review ────────────────────────────────────────────────────────────────────
export const approveRecord = (id, note) => api.post(`/review/${id}/approve/`, { note });
export const rejectRecord = (id, note) => api.post(`/review/${id}/reject/`, { note });
export const flagRecord = (id, reason, note) =>
  api.post(`/review/${id}/flag/`, { reason, note });
export const lockRecord = (id) => api.post(`/review/${id}/lock/`);
export const bulkApprove = (ids) => api.post('/review/bulk-approve/', { ids });
export const getRecordHistory = (id) => api.get(`/review/${id}/history/`);
