import { useState, useEffect, useCallback } from 'react';
import {
  getEmissions, approveRecord, rejectRecord, flagRecord, lockRecord, bulkApprove,
  getRecordHistory, updateEmission,
} from '../api';
import { useToast } from '../context/ToastContext';

const SCOPE_MAP = { SCOPE_1: '1', SCOPE_2: '2', SCOPE_3: '3' };
const STATUS_OPTIONS = ['', 'PENDING', 'FLAGGED', 'APPROVED', 'REJECTED', 'LOCKED'];
const SCOPE_OPTIONS  = ['', 'SCOPE_1', 'SCOPE_2', 'SCOPE_3'];
const SOURCE_OPTIONS = [
  '', 'SAP_FUEL', 'SAP_PROCUREMENT', 'UTILITY_ELECTRICITY',
  'TRAVEL_FLIGHT', 'TRAVEL_HOTEL', 'TRAVEL_GROUND',
];
const FLAG_REASONS = [
  'unit_mismatch', 'outlier_value', 'missing_ref', 'duplicate', 'date_gap', 'other',
];

function ScopeBadge({ scope }) {
  const n = SCOPE_MAP[scope] || '?';
  return <span className={`scope-badge scope-${n.toLowerCase()}`}>S{n}</span>;
}

function StatusBadge({ status }) {
  return <span className={`badge badge-${status.toLowerCase()}`}>{status}</span>;
}

function RecordModal({ record, onClose, onRefresh }) {
  const [note, setNote] = useState(record.analyst_note || '');
  const [flagReason, setFlagReason] = useState(record.flag_reason || 'other');
  const [history, setHistory] = useState([]);
  const [tab, setTab] = useState('detail'); // detail | raw | history | edit
  const [editQty, setEditQty] = useState(record.activity_quantity);
  const [saving, setSaving] = useState(false);
  const toast = useToast();
  const locked = record.status === 'LOCKED';

  useEffect(() => {
    getRecordHistory(record.id).then(r => setHistory(r.data)).catch(() => {});
  }, [record.id]);

  const doAction = async (action) => {
    setSaving(true);
    try {
      if (action === 'approve') await approveRecord(record.id, note);
      if (action === 'reject')  await rejectRecord(record.id, note);
      if (action === 'flag')    await flagRecord(record.id, flagReason, note);
      if (action === 'lock')    await lockRecord(record.id);
      if (action === 'save') {
        await updateEmission(record.id, { activity_quantity: editQty, analyst_note: note });
      }
      toast({ type: 'success', title: `Record ${action}d successfully` });
      onRefresh();
      onClose();
    } catch (e) {
      toast({ type: 'error', title: 'Action failed', message: e.response?.data?.error || e.message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal">
        <div className="modal-header">
          <div>
            <div className="modal-title">
              <ScopeBadge scope={record.scope} />
              {' '}{record.source_type_display}
            </div>
            <div className="text-muted mt-1">
              {record.description || 'No description'}
            </div>
          </div>
          <div className="flex gap-2">
            <StatusBadge status={record.status} />
            <button className="modal-close" onClick={onClose}>×</button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-4" style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: 12 }}>
          {[['detail','Details'],['raw','Raw Data'],['history','Audit Trail'],['edit','Edit']].map(([t,l]) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              disabled={t === 'edit' && locked}
              style={{
                background: 'none', border: 'none',
                color: tab === t ? 'var(--color-primary)' : 'var(--text-muted)',
                fontWeight: tab === t ? 700 : 400,
                fontSize: 13, padding: '4px 8px', borderRadius: 6,
                borderBottom: tab === t ? '2px solid var(--color-primary)' : '2px solid transparent',
                cursor: t === 'edit' && locked ? 'not-allowed' : 'pointer',
              }}
            >{l}</button>
          ))}
        </div>

        {/* Detail tab */}
        {tab === 'detail' && (
          <>
            <div className="detail-grid">
              <div className="detail-field">
                <label>Activity Date</label>
                <div className="value">{record.activity_date}</div>
              </div>
              <div className="detail-field">
                <label>Quantity</label>
                <div className="value font-mono">
                  {parseFloat(record.activity_quantity).toLocaleString()} {record.activity_unit}
                </div>
              </div>
              <div className="detail-field">
                <label>CO₂e</label>
                <div className="value font-mono" style={{ color: 'var(--color-primary)' }}>
                  {parseFloat(record.total_co2e_kg).toFixed(2)} kg ({record.total_co2e_tonnes?.toFixed(4)} t)
                </div>
              </div>
              <div className="detail-field">
                <label>Emission Factor</label>
                <div className="value font-mono">
                  {parseFloat(record.emission_factor_value).toFixed(6)} kgCO₂e / {record.activity_unit}
                </div>
              </div>
              <div className="detail-field">
                <label>EF Source</label>
                <div className="value">{record.emission_factor_source || '—'}</div>
              </div>
              <div className="detail-field">
                <label>GHG Category</label>
                <div className="value font-mono" style={{ fontSize: 11 }}>{record.ghg_category}</div>
              </div>
              <div className="detail-field">
                <label>Location</label>
                <div className="value">{record.location || '—'}</div>
              </div>
              <div className="detail-field">
                <label>Vendor / Ref</label>
                <div className="value">{record.vendor || record.source_ref || '—'}</div>
              </div>
              <div className="detail-field">
                <label>Source File</label>
                <div className="value font-mono" style={{ fontSize: 11 }}>{record.source_file}</div>
              </div>
              <div className="detail-field">
                <label>Manually Edited</label>
                <div className="value">{record.is_manually_edited ? '⚠️ Yes' : 'No'}</div>
              </div>
              {record.reporting_period_start && (
                <div className="detail-field">
                  <label>Reporting Period</label>
                  <div className="value">{record.reporting_period_start} → {record.reporting_period_end}</div>
                </div>
              )}
              {record.reviewed_by_username && (
                <div className="detail-field">
                  <label>Reviewed by</label>
                  <div className="value">{record.reviewed_by_username} on {new Date(record.reviewed_at).toLocaleString()}</div>
                </div>
              )}
            </div>

            {record.analyst_note && (
              <div style={{
                padding: '10px 14px', background: 'rgba(245,158,11,0.08)',
                border: '1px solid rgba(245,158,11,0.2)', borderRadius: 8,
                fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12,
              }}>
                <strong style={{ color: 'var(--color-flagged)' }}>Note:</strong> {record.analyst_note}
              </div>
            )}

            {!locked && (
              <>
                <div className="form-group">
                  <label className="form-label">Analyst Note</label>
                  <textarea
                    className="input"
                    rows={2}
                    placeholder="Add a note..."
                    value={note}
                    onChange={e => setNote(e.target.value)}
                    style={{ resize: 'vertical' }}
                  />
                </div>
                {record.status === 'PENDING' || record.status === 'FLAGGED' ? (
                  <div className="flex gap-2">
                    <button id="btn-approve" className="btn btn-approve" onClick={() => doAction('approve')} disabled={saving}>
                      ✓ Approve
                    </button>
                    <button id="btn-reject" className="btn btn-reject" onClick={() => doAction('reject')} disabled={saving}>
                      ✗ Reject
                    </button>
                    <div style={{ flex: 1 }}>
                      <select
                        className="input select"
                        value={flagReason}
                        onChange={e => setFlagReason(e.target.value)}
                        style={{ marginBottom: 6 }}
                      >
                        {FLAG_REASONS.map(r => <option key={r} value={r}>{r.replace(/_/g,' ')}</option>)}
                      </select>
                    </div>
                    <button id="btn-flag" className="btn btn-flag" onClick={() => doAction('flag')} disabled={saving}>
                      ⚑ Flag
                    </button>
                  </div>
                ) : record.status === 'APPROVED' ? (
                  <button id="btn-lock" className="btn btn-secondary" onClick={() => doAction('lock')} disabled={saving}>
                    🔒 Lock for Audit
                  </button>
                ) : null}
              </>
            )}
            {locked && (
              <div style={{ padding: '12px', background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 8, fontSize: 12, color: 'var(--color-locked)' }}>
                🔒 This record is locked for audit. No further changes are permitted.
              </div>
            )}
          </>
        )}

        {/* Raw JSON tab */}
        {tab === 'raw' && (
          <div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
              Original parsed row — preserved exactly as received from source file
            </div>
            <pre className="raw-json">{JSON.stringify(record, null, 2)}</pre>
          </div>
        )}

        {/* History tab */}
        {tab === 'history' && (
          <div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
              Field-level change log (django-simple-history)
            </div>
            {history.length === 0 ? (
              <div className="empty-state" style={{ padding: 30 }}>
                <div className="empty-state-text">No history yet</div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {history.map((h, i) => (
                  <div key={i} style={{
                    padding: '10px 12px',
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 8,
                    fontSize: 12,
                  }}>
                    <div className="flex-between">
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        {h.history_type} — {h.changed_by || 'system'}
                      </span>
                      <span className="text-muted">{new Date(h.history_date).toLocaleString()}</span>
                    </div>
                    <div className="text-muted mt-1">Status: {h.status}</div>
                    {h.analyst_note && <div style={{ color: 'var(--text-secondary)', marginTop: 2 }}>Note: {h.analyst_note}</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Edit tab */}
        {tab === 'edit' && !locked && (
          <div>
            <div style={{ fontSize: 12, color: 'var(--color-flagged)', marginBottom: 12 }}>
              ⚠️ Editing will mark this record as manually edited in the audit trail.
            </div>
            <div className="form-group">
              <label className="form-label">Activity Quantity ({record.activity_unit})</label>
              <input
                type="number"
                className="input"
                value={editQty}
                onChange={e => setEditQty(e.target.value)}
                step="any"
              />
            </div>
            <div className="form-group">
              <label className="form-label">Analyst Note (required for edits)</label>
              <textarea
                className="input"
                rows={3}
                value={note}
                onChange={e => setNote(e.target.value)}
                placeholder="Explain why this value is being edited..."
              />
            </div>
            <button id="btn-save-edit" className="btn btn-primary" onClick={() => doAction('save')} disabled={saving || !note.trim()}>
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ReviewPage() {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [filters, setFilters] = useState({
    status: '', scope: '', source_type: '', search: '',
  });
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const toast = useToast();

  const fetch = useCallback(() => {
    setLoading(true);
    const params = { page, ...Object.fromEntries(Object.entries(filters).filter(([,v]) => v)) };
    getEmissions(params)
      .then(r => {
        const data = r.data;
        if (data.results) {
          setRecords(data.results);
          setTotalCount(data.count);
        } else {
          setRecords(data);
          setTotalCount(data.length);
        }
      })
      .finally(() => setLoading(false));
  }, [filters, page]);

  useEffect(() => { fetch(); }, [fetch]);

  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    const lockable = records.filter(r => !['LOCKED','REJECTED'].includes(r.status));
    setSelectedIds(new Set(lockable.map(r => r.id)));
  };

  const handleBulkApprove = async () => {
    if (selectedIds.size === 0) return;
    try {
      const { data } = await bulkApprove([...selectedIds]);
      toast({ type: 'success', title: `Approved ${data.approved} records` });
      setSelectedIds(new Set());
      fetch();
    } catch (e) {
      toast({ type: 'error', title: 'Bulk approve failed' });
    }
  };

  const filterChange = (key, val) => {
    setFilters(f => ({ ...f, [key]: val }));
    setPage(1);
  };

  const totalPages = Math.ceil(totalCount / 50);

  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h1 className="page-title">Review Queue</h1>
          <p className="page-subtitle">
            {totalCount} records · Approve, reject, or flag before audit lock
          </p>
        </div>
        {selectedIds.size > 0 && (
          <div className="flex gap-2">
            <span style={{ fontSize: 13, color: 'var(--text-muted)', alignSelf: 'center' }}>
              {selectedIds.size} selected
            </span>
            <button id="btn-bulk-approve" className="btn btn-approve" onClick={handleBulkApprove}>
              ✓ Bulk Approve
            </button>
            <button className="btn btn-secondary" onClick={() => setSelectedIds(new Set())}>
              ✕ Clear
            </button>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="filter-bar">
        <div className="search-box">
          <span className="search-icon">🔍</span>
          <input
            id="search-input"
            className="input"
            placeholder="Search description, vendor, location..."
            value={filters.search}
            onChange={e => filterChange('search', e.target.value)}
          />
        </div>

        <select id="filter-status" className="input select" style={{ width: 150 }}
          value={filters.status} onChange={e => filterChange('status', e.target.value)}>
          <option value="">All Statuses</option>
          {STATUS_OPTIONS.filter(Boolean).map(s => <option key={s} value={s}>{s}</option>)}
        </select>

        <select id="filter-scope" className="input select" style={{ width: 140 }}
          value={filters.scope} onChange={e => filterChange('scope', e.target.value)}>
          <option value="">All Scopes</option>
          {SCOPE_OPTIONS.filter(Boolean).map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
        </select>

        <select id="filter-source" className="input select" style={{ width: 200 }}
          value={filters.source_type} onChange={e => filterChange('source_type', e.target.value)}>
          <option value="">All Sources</option>
          {SOURCE_OPTIONS.filter(Boolean).map(s => <option key={s} value={s}>{s.replace(/_/g,' ')}</option>)}
        </select>

        <button className="btn btn-secondary btn-sm" onClick={() => {
          setFilters({ status: '', scope: '', source_type: '', search: '' });
          setPage(1);
        }}>↺ Reset</button>

        <button className="btn btn-secondary btn-sm" onClick={fetch}>↻ Refresh</button>
        <button className="btn btn-secondary btn-sm" onClick={selectAll}>☑ Select All</button>
      </div>

      {loading ? (
        <div className="loading-state"><div className="spinner spinner-lg" /><span>Loading records...</span></div>
      ) : records.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🔍</div>
          <div className="empty-state-text">No records match the current filters.</div>
        </div>
      ) : (
        <>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th style={{ width: 36 }}>
                    <input type="checkbox" onChange={e => e.target.checked ? selectAll() : setSelectedIds(new Set())} />
                  </th>
                  <th>Scope</th>
                  <th>Source</th>
                  <th>Date</th>
                  <th>Description</th>
                  <th>Quantity</th>
                  <th>CO₂e</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {records.map(r => (
                  <tr
                    key={r.id}
                    className={r.status === 'FLAGGED' ? 'flagged-row' : ''}
                  >
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(r.id)}
                        onChange={() => toggleSelect(r.id)}
                        disabled={['LOCKED','REJECTED'].includes(r.status)}
                      />
                    </td>
                    <td><ScopeBadge scope={r.scope} /></td>
                    <td>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        {r.source_type_display}
                      </span>
                    </td>
                    <td className="td-mono">{r.activity_date}</td>
                    <td>
                      <div style={{ maxWidth: 280 }} className="truncate" title={r.description}>
                        {r.description || <span className="text-muted">—</span>}
                      </div>
                      {r.flag_reason && (
                        <div style={{ fontSize: 10, color: 'var(--color-flagged)', marginTop: 2 }}>
                          ⚑ {r.flag_reason.replace(/_/g, ' ')}
                        </div>
                      )}
                    </td>
                    <td className="td-mono">
                      {parseFloat(r.activity_quantity).toLocaleString()} {r.activity_unit}
                    </td>
                    <td className="td-mono" style={{ color: 'var(--color-primary)' }}>
                      {parseFloat(r.total_co2e_kg).toFixed(1)} kg
                    </td>
                    <td><StatusBadge status={r.status} /></td>
                    <td>
                      <div className="flex gap-2">
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => setSelected(r)}
                        >
                          View
                        </button>
                        {(r.status === 'PENDING' || r.status === 'FLAGGED') && (
                          <>
                            <button
                              className="btn btn-approve btn-sm"
                              onClick={async () => {
                                await approveRecord(r.id, '');
                                toast({ type: 'success', title: 'Approved' });
                                fetch();
                              }}
                            >✓</button>
                            <button
                              className="btn btn-reject btn-sm"
                              onClick={async () => {
                                await rejectRecord(r.id, '');
                                toast({ type: 'success', title: 'Rejected' });
                                fetch();
                              }}
                            >✗</button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex-center gap-3" style={{ marginTop: 16, justifyContent: 'center' }}>
              <button className="btn btn-secondary btn-sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
              <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>Page {page} of {totalPages}</span>
              <button className="btn btn-secondary btn-sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next →</button>
            </div>
          )}
        </>
      )}

      {selected && (
        <RecordModal
          record={selected}
          onClose={() => setSelected(null)}
          onRefresh={fetch}
        />
      )}
    </div>
  );
}
