import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, LineChart, Line
} from 'recharts';
import { getDashboardSummary, getDashboardTimeline } from '../api';

const SCOPE_COLORS = {
  SCOPE_1: 'var(--color-scope1)',
  SCOPE_2: 'var(--color-scope2)',
  SCOPE_3: 'var(--color-scope3)',
};

const SOURCE_LABELS = {
  SAP_FUEL: '⛽ SAP Fuel',
  SAP_PROCUREMENT: '📦 SAP Procurement',
  UTILITY_ELECTRICITY: '⚡ Electricity',
  TRAVEL_FLIGHT: '✈️ Flights',
  TRAVEL_HOTEL: '🏨 Hotels',
  TRAVEL_GROUND: '🚕 Ground',
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border-default)',
      borderRadius: 8, padding: '10px 14px', fontSize: 12,
    }}>
      <div style={{ fontWeight: 600, marginBottom: 6, color: 'var(--text-primary)' }}>{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ color: p.color, marginBottom: 2 }}>
          {p.name}: {p.value.toFixed(3)} tCO₂e
        </div>
      ))}
    </div>
  );
};

export default function DashboardPage() {
  const [summary, setSummary] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([getDashboardSummary(), getDashboardTimeline()])
      .then(([s, t]) => {
        setSummary(s.data);
        setTimeline(t.data);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="loading-state">
      <div className="spinner spinner-lg" />
      <span>Loading dashboard...</span>
    </div>
  );

  const { by_scope = {}, by_status = {}, by_source = {}, total_co2e_tonnes = 0 } = summary || {};

  const kpis = [
    {
      label: 'Total Emissions',
      value: total_co2e_tonnes.toFixed(1),
      unit: 'tCO₂e',
      icon: '🌍',
      color: 'var(--color-primary)',
    },
    {
      label: 'Scope 1 — Direct',
      value: (by_scope['SCOPE_1'] || 0).toFixed(2),
      unit: 'tCO₂e',
      icon: '🔥',
      color: 'var(--color-scope1)',
    },
    {
      label: 'Scope 2 — Electricity',
      value: (by_scope['SCOPE_2'] || 0).toFixed(2),
      unit: 'tCO₂e',
      icon: '⚡',
      color: 'var(--color-scope2)',
    },
    {
      label: 'Scope 3 — Value Chain',
      value: (by_scope['SCOPE_3'] || 0).toFixed(2),
      unit: 'tCO₂e',
      icon: '✈️',
      color: 'var(--color-scope3)',
    },
    {
      label: 'Pending Review',
      value: by_status['PENDING'] || 0,
      unit: 'records',
      icon: '⏳',
      color: 'var(--color-pending)',
    },
    {
      label: 'Flagged',
      value: by_status['FLAGGED'] || 0,
      unit: 'records',
      icon: '⚠️',
      color: 'var(--color-flagged)',
    },
    {
      label: 'Approved',
      value: by_status['APPROVED'] || 0,
      unit: 'records',
      icon: '✅',
      color: 'var(--color-approved)',
    },
    {
      label: 'Locked for Audit',
      value: by_status['LOCKED'] || 0,
      unit: 'records',
      icon: '🔒',
      color: 'var(--color-locked)',
    },
  ];

  const sourceData = Object.entries(by_source).map(([key, val]) => ({
    name: SOURCE_LABELS[key] || key,
    co2e: val.co2e_kg ? (val.co2e_kg / 1000).toFixed(3) : 0,
    count: val.count,
  }));

  const timelineForChart = timeline.map(row => ({
    month: row.month,
    'Scope 1': row.SCOPE_1 || 0,
    'Scope 2': row.SCOPE_2 || 0,
    'Scope 3': row.SCOPE_3 || 0,
  }));

  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h1 className="page-title">Emissions Dashboard</h1>
          <p className="page-subtitle">
            Real-time view across all ingested and approved activity data
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/ingest')}>
          + Ingest Data
        </button>
      </div>

      {/* KPI Grid */}
      <div className="kpi-grid">
        {kpis.map(k => (
          <div
            className="kpi-card"
            key={k.label}
            style={{ '--kpi-color': k.color }}
          >
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value">{k.value.toLocaleString()}</div>
            <div className="kpi-unit">{k.unit}</div>
            <div className="kpi-icon">{k.icon}</div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
        {/* Timeline chart */}
        <div className="chart-container" style={{ gridColumn: timeline.length > 0 ? '1 / -1' : '1' }}>
          <div className="card-header">
            <span className="card-title">Monthly Emissions by Scope</span>
            <span className="text-muted">tCO₂e per month</span>
          </div>
          <div className="chart-legend">
            {[['SCOPE_1', '🔥 Scope 1', 'var(--color-scope1)'],
              ['SCOPE_2', '⚡ Scope 2', 'var(--color-scope2)'],
              ['SCOPE_3', '✈️ Scope 3', 'var(--color-scope3)']].map(([k, label, color]) => (
              <div className="legend-item" key={k}>
                <div className="legend-dot" style={{ background: color }} />
                {label}
              </div>
            ))}
          </div>
          {timelineForChart.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={timelineForChart} barGap={2}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                <XAxis dataKey="month" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
                <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 11 }} unit=" t" />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="Scope 1" fill="var(--color-scope1)" radius={[3,3,0,0]} />
                <Bar dataKey="Scope 2" fill="var(--color-scope2)" radius={[3,3,0,0]} />
                <Bar dataKey="Scope 3" fill="var(--color-scope3)" radius={[3,3,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state">
              <div className="empty-state-icon">📊</div>
              <div className="empty-state-text">No emissions data yet. Ingest a file to get started.</div>
            </div>
          )}
        </div>
      </div>

      {/* Source breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <div className="chart-container">
          <div className="card-header">
            <span className="card-title">Emissions by Source</span>
            <span className="text-muted">tCO₂e</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={sourceData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" horizontal={false} />
              <XAxis type="number" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} unit=" t" />
              <YAxis dataKey="name" type="category" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} width={120} />
              <Tooltip
                formatter={(v) => [`${v} tCO₂e`]}
                contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8 }}
                labelStyle={{ color: 'var(--text-primary)' }}
              />
              <Bar dataKey="co2e" fill="var(--color-primary)" radius={[0,3,3,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-container">
          <div className="card-header">
            <span className="card-title">Review Status</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '8px 0' }}>
            {[
              ['PENDING', 'Pending Review', 'var(--color-pending)'],
              ['FLAGGED', 'Flagged', 'var(--color-flagged)'],
              ['APPROVED', 'Approved', 'var(--color-approved)'],
              ['REJECTED', 'Rejected', 'var(--color-rejected)'],
              ['LOCKED', 'Locked', 'var(--color-locked)'],
            ].map(([key, label, color]) => {
              const count = by_status[key] || 0;
              const total = summary?.total_records || 1;
              const pct = Math.round((count / total) * 100);
              return (
                <div key={key}>
                  <div className="flex-between mb-1">
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{label}</span>
                    <span style={{ fontSize: 12, fontWeight: 600, color }}>{count}</span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{
                      width: `${pct}%`,
                      background: color,
                    }} />
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{ marginTop: 16 }}>
            <button className="btn btn-primary w-full" onClick={() => navigate('/review')}>
              Go to Review Queue →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
