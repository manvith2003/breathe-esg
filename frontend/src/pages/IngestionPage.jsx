import { useState, useCallback, useEffect } from 'react';
import { uploadFile, getBatches } from '../api';
import { useToast } from '../context/ToastContext';

const SOURCES = [
  {
    key: 'SAP_FUEL',
    icon: '⛽',
    color: 'var(--color-scope1)',
    title: 'SAP Fuel & Procurement',
    desc: 'Pipe-delimited ABAP flat file export (EKKO/EKPO/MSEG)',
    accept: '.csv,.txt',
    hint: 'Supports pipe (|) or comma delimited; German column aliases; DD.MM.YYYY dates',
  },
  {
    key: 'UTILITY',
    icon: '⚡',
    color: 'var(--color-scope2)',
    title: 'Utility Electricity',
    desc: 'Green Button–style portal CSV export',
    accept: '.csv',
    hint: 'Non-calendar billing periods supported; MWh and kWh; estimated reading flags',
  },
  {
    key: 'TRAVEL',
    icon: '✈️',
    color: 'var(--color-scope3)',
    title: 'Corporate Travel (Concur)',
    desc: 'Concur Expense File Export (CSV bulk export)',
    accept: '.csv',
    hint: 'Flights, hotels, ground transport; haversine distance fallback for missing km',
  },
];

function UploadCard({ source, onUploadComplete }) {
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const toast = useToast();

  const handleFile = async (file) => {
    if (!file) return;
    setUploading(true);
    setResult(null);
    try {
      const { data } = await uploadFile(file, source.key);
      setResult(data);
      toast({
        type: data.status === 'DONE' ? 'success' : 'warning',
        title: `${source.title} — ${data.status}`,
        message: `${data.row_count} rows, ${data.error_count} errors, ${data.warning_count} warnings`,
      });
      onUploadComplete?.();
    } catch (e) {
      toast({ type: 'error', title: 'Upload failed', message: e.response?.data?.error || e.message });
    } finally {
      setUploading(false);
    }
  };

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDrag(false);
    handleFile(e.dataTransfer.files[0]);
  }, []);

  const onInputChange = (e) => handleFile(e.target.files[0]);

  return (
    <div className="upload-card">
      <div className="upload-card-header">
        <div className="upload-card-icon" style={{ background: source.color + '22' }}>
          {source.icon}
        </div>
        <div>
          <div className="upload-card-title">{source.title}</div>
          <div className="upload-card-desc">{source.desc}</div>
        </div>
      </div>

      <label
        id={`drop-${source.key}`}
        className={`drop-zone ${drag ? 'drag-active' : ''}`}
        onDragOver={e => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        style={{ cursor: uploading ? 'not-allowed' : 'pointer' }}
      >
        <input
          type="file"
          accept={source.accept}
          style={{ display: 'none' }}
          onChange={onInputChange}
          disabled={uploading}
        />
        {uploading ? (
          <>
            <div className="drop-zone-icon"><div className="spinner" style={{ width: 28, height: 28, borderWidth: 3 }} /></div>
            <div className="drop-zone-text">Processing file...</div>
          </>
        ) : (
          <>
            <div className="drop-zone-icon">📂</div>
            <div className="drop-zone-text">Drop file here or click to browse</div>
            <div className="drop-zone-hint">{source.hint}</div>
          </>
        )}
      </label>

      {result && (
        <div className="batch-status-card" style={{
          borderLeft: `3px solid ${result.error_count === result.row_count && result.row_count > 0 ? 'var(--color-rejected)' : result.error_count > 0 ? 'var(--color-flagged)' : 'var(--color-approved)'}`
        }}>
          <div className="flex-between">
            <span style={{ fontWeight: 600, fontSize: 13 }}>{result.file_name}</span>
            <span className={`badge badge-${result.status === 'DONE' ? 'approved' : 'rejected'}`}>
              {result.status}
            </span>
          </div>
          <div className="batch-meta">
            <span className="batch-meta-item">Rows: <strong>{result.row_count}</strong></span>
            <span className="batch-meta-item" style={{ color: result.error_count > 0 ? 'var(--color-rejected)' : undefined }}>
              Errors: <strong>{result.error_count}</strong>
            </span>
            <span className="batch-meta-item" style={{ color: result.warning_count > 0 ? 'var(--color-flagged)' : undefined }}>
              Warnings: <strong>{result.warning_count}</strong>
            </span>
          </div>
          {result.processing_log && result.processing_log !== 'All rows processed successfully.' && (
            <div className="raw-json" style={{ marginTop: 8, fontSize: 11 }}>
              {result.processing_log}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function BatchHistoryTable({ batches }) {
  const STATUS_COLORS = {
    DONE: 'approved', FAILED: 'rejected', PROCESSING: 'pending', PENDING: 'pending',
  };

  return (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            <th>File</th>
            <th>Source</th>
            <th>Uploaded</th>
            <th>Rows</th>
            <th>Errors</th>
            <th>Warnings</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {batches.map(b => (
            <tr key={b.id}>
              <td className="td-mono">{b.file_name}</td>
              <td><span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{b.source_type_display}</span></td>
              <td className="text-muted">{new Date(b.uploaded_at).toLocaleString()}</td>
              <td style={{ fontWeight: 600 }}>{b.row_count}</td>
              <td style={{ color: b.error_count > 0 ? 'var(--color-rejected)' : 'var(--text-muted)' }}>
                {b.error_count}
              </td>
              <td style={{ color: b.warning_count > 0 ? 'var(--color-flagged)' : 'var(--text-muted)' }}>
                {b.warning_count}
              </td>
              <td>
                <span className={`badge badge-${STATUS_COLORS[b.status] || 'pending'}`}>
                  {b.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function IngestionPage() {
  const [batches, setBatches] = useState([]);
  const [loadingBatches, setLoadingBatches] = useState(true);

  const fetchBatches = useCallback(() => {
    getBatches().then(r => setBatches(r.data.results || r.data))
                .finally(() => setLoadingBatches(false));
  }, []);

  useEffect(() => { fetchBatches(); }, [fetchBatches]);

  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h1 className="page-title">Ingest Data</h1>
          <p className="page-subtitle">
            Upload emission source files for parsing, normalization, and review
          </p>
        </div>
      </div>

      {/* Info Banner */}
      <div className="card-glass" style={{
        marginBottom: 24,
        borderColor: 'rgba(16,185,129,0.2)',
        background: 'rgba(16,185,129,0.04)',
      }}>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
          <strong style={{ color: 'var(--color-primary)' }}>How ingestion works:</strong>
          {' '}Upload a file for any of the three source types below.
          The system parses it, normalizes units to SI base, classifies GHG scope,
          applies DEFRA 2023 emission factors, and queues all rows for analyst review.
          Rows with issues are automatically flagged.
        </div>
      </div>

      {/* Upload cards */}
      <div className="upload-cards">
        {SOURCES.map(s => (
          <UploadCard key={s.key} source={s} onUploadComplete={fetchBatches} />
        ))}
      </div>

      {/* Batch history */}
      <div className="card-header" style={{ marginBottom: 12 }}>
        <h2 style={{ fontSize: 15, fontWeight: 700 }}>Upload History</h2>
        <button className="btn btn-secondary btn-sm" onClick={fetchBatches}>↻ Refresh</button>
      </div>

      {loadingBatches ? (
        <div className="loading-state"><div className="spinner" /></div>
      ) : batches.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📁</div>
          <div className="empty-state-text">No uploads yet. Upload a file above to get started.</div>
        </div>
      ) : (
        <BatchHistoryTable batches={batches} />
      )}
    </div>
  );
}
