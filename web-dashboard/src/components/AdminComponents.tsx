/**
 * AdminDashboard.tsx — KPI cards + quick navigation for admin section
 * CIEManagement.tsx  — CRUD table for CIE periods with date pickers
 * FileUploadForm.tsx — Reusable CSV upload with preview & validation
 * ReportsPage.tsx    — Summary stats + recharts attendance trend charts
 *
 * All four exported from this single file to keep the bundle tidy.
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend
} from 'recharts';
import {
  Users, BookOpen, Calendar, TrendingUp, TrendingDown,
  Plus, Edit2, Trash2, Save, X, Upload, FileText,
  CheckCircle, AlertTriangle, Download, RefreshCw,
  BarChart2, PieChart as PieIcon, Activity, ChevronRight,
  ClipboardList, Database
} from 'lucide-react';

// ─────────────────────────────────────────────────────────────────────────────
//  Shared style helpers
// ─────────────────────────────────────────────────────────────────────────────

const inputSx: React.CSSProperties = {
  width: '100%', padding: '9px 12px', borderRadius: '10px',
  border: '1.5px solid #e2e8f0', background: '#fff',
  fontSize: '0.82rem', color: '#1e293b', outline: 'none',
  boxSizing: 'border-box',
};

const btnPrimary: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: '7px',
  padding: '9px 18px', borderRadius: '11px', border: 'none', cursor: 'pointer',
  background: 'linear-gradient(135deg,#6366F1 0%,#818CF8 100%)',
  color: '#fff', fontSize: '0.82rem', fontWeight: 700,
  boxShadow: '0 3px 12px #6366F130',
};

const btnSecondary: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: '7px',
  padding: '9px 18px', borderRadius: '11px', cursor: 'pointer',
  background: '#F8FAFC', color: '#475569', fontSize: '0.82rem', fontWeight: 600,
  border: '1.5px solid #E2E8F0',
};

const btnDanger: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: '7px',
  padding: '7px 13px', borderRadius: '9px', cursor: 'pointer',
  background: '#FEF2F2', color: '#DC2626', fontSize: '0.78rem', fontWeight: 600,
  border: '1.5px solid #FECACA',
};

// ─────────────────────────────────────────────────────────────────────────────
//  1. AdminDashboard
// ─────────────────────────────────────────────────────────────────────────────

export interface AdminKPIs {
  cie_count: number;
  class_count: number;
  student_count: number;
  faculty_count: number;
  avg_attendance_pct: number;
  critical_students: number;
  total_periods_today: number;
  active_periods_now: number;
}

interface AdminDashboardProps {
  kpis: AdminKPIs;
  loading?: boolean;
  onRefresh?: () => void;
  onNavigate?: (section: 'cie' | 'classes' | 'students' | 'reports' | 'upload') => void;
}

const PALETTE = ['#6366F1','#22C55E','#F59E0B','#EF4444','#8B5CF6','#14B8A6'];

function KPICard({ label, value, sub, hex, Icon }: {
  label: string; value: string | number; sub?: string;
  hex: string; Icon: React.FC<any>;
}) {
  return (
    <div style={{
      borderRadius: '18px', padding: '18px 20px',
      background: `linear-gradient(135deg,${hex}10 0%,${hex}06 100%)`,
      border: `1.5px solid ${hex}28`, position: 'relative', overflow: 'hidden',
    }}>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '3px', background: hex, borderRadius: '18px 18px 0 0' }} />
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
        <div>
          <p style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#94a3b8', marginBottom: '6px' }}>{label}</p>
          <p style={{ fontSize: '2rem', fontWeight: 900, color: hex, lineHeight: 1, fontFamily: 'monospace' }}>{value}</p>
          {sub && <p style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '5px' }}>{sub}</p>}
        </div>
        <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: `${hex}18`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <Icon size={20} style={{ color: hex }} />
        </div>
      </div>
    </div>
  );
}

export const AdminDashboard: React.FC<AdminDashboardProps> = ({
  kpis, loading = false, onRefresh, onNavigate,
}) => {
  const avgBand = kpis.avg_attendance_pct >= 85 ? '#22C55E' : kpis.avg_attendance_pct >= 75 ? '#F59E0B' : '#EF4444';

  const shortcuts = [
    { label: 'Manage CIEs',     icon: ClipboardList, section: 'cie' as const,     hex: '#6366F1' },
    { label: 'Upload Timetable',icon: Upload,         section: 'upload' as const,  hex: '#14B8A6' },
    { label: 'View Reports',    icon: BarChart2,      section: 'reports' as const, hex: '#F59E0B' },
    { label: 'Student List',    icon: Users,          section: 'students' as const,hex: '#8B5CF6' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <p style={{ fontSize: '0.7rem', fontWeight: 600, letterSpacing: '0.14em', textTransform: 'uppercase', color: '#94a3b8', marginBottom: '4px' }}>Admin Panel</p>
          <h1 style={{ fontSize: '1.7rem', fontWeight: 900, color: '#1e293b' }}>System Overview</h1>
        </div>
        {onRefresh && (
          <button onClick={onRefresh} disabled={loading} style={btnSecondary}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            Refresh
          </button>
        )}
      </div>

      {/* KPI grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: '12px' }}>
        <KPICard label="CIE Periods"     value={kpis.cie_count}            sub="this semester"         hex="#6366F1" Icon={ClipboardList} />
        <KPICard label="Classes"          value={kpis.class_count}           sub="active sections"       hex="#14B8A6" Icon={BookOpen} />
        <KPICard label="Students"         value={kpis.student_count}         sub="registered"            hex="#8B5CF6" Icon={Users} />
        <KPICard label="Faculty"          value={kpis.faculty_count}         sub="teaching staff"        hex="#F59E0B" Icon={Activity} />
        <KPICard label="Avg Attendance"   value={`${kpis.avg_attendance_pct.toFixed(1)}%`} sub="all courses" hex={avgBand} Icon={TrendingUp} />
        <KPICard label="Critical Students"value={kpis.critical_students}    sub="below 75%"             hex="#EF4444" Icon={AlertTriangle} />
        <KPICard label="Periods Today"    value={kpis.total_periods_today}  sub="scheduled"             hex="#6366F1" Icon={Calendar} />
        <KPICard label="Active Now"       value={kpis.active_periods_now}   sub="in session"            hex="#22C55E" Icon={Activity} />
      </div>

      {/* Quick shortcuts */}
      <div>
        <p style={{ fontSize: '0.72rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '12px' }}>Quick Actions</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: '10px' }}>
          {shortcuts.map(({ label, icon: Icon, section, hex }) => (
            <button
              key={section}
              onClick={() => onNavigate?.(section)}
              style={{
                display: 'flex', alignItems: 'center', gap: '10px', padding: '14px 16px',
                borderRadius: '14px', cursor: 'pointer', border: `1.5px solid ${hex}25`,
                background: `${hex}0c`, textAlign: 'left',
              }}
            >
              <div style={{ width: '34px', height: '34px', borderRadius: '10px', background: `${hex}20`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <Icon size={17} style={{ color: hex }} />
              </div>
              <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#1e293b' }}>{label}</span>
              <ChevronRight size={14} style={{ color: '#94a3b8', marginLeft: 'auto' }} />
            </button>
          ))}
        </div>
      </div>

      <style>{`.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
//  2. CIEManagement
// ─────────────────────────────────────────────────────────────────────────────

export interface CIERecord {
  cie_id: string;
  name: string;
  start_date: string;
  end_date: string;
  active_status: boolean;
  description?: string;
}

interface CIEManagementProps {
  records: CIERecord[];
  loading?: boolean;
  onCreate?: (data: Omit<CIERecord, 'cie_id'>) => Promise<void>;
  onUpdate?: (id: string, data: Partial<CIERecord>) => Promise<void>;
  onDelete?: (id: string) => Promise<void>;
  onRefresh?: () => void;
}

const EMPTY_CIE: Omit<CIERecord, 'cie_id'> = {
  name: '', start_date: '', end_date: '', active_status: true, description: '',
};

function CIEForm({ initial, onSave, onCancel, saving }: {
  initial: Partial<CIERecord>;
  onSave: (d: Omit<CIERecord,'cie_id'>) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const [form, setForm] = useState<Omit<CIERecord,'cie_id'>>({
    name: initial.name ?? '',
    start_date: initial.start_date ?? '',
    end_date: initial.end_date ?? '',
    active_status: initial.active_status ?? true,
    description: initial.description ?? '',
  });
  const [errors, setErrors] = useState<Record<string,string>>({});

  const validate = () => {
    const e: Record<string,string> = {};
    if (!form.name.trim())        e.name       = 'Name is required';
    if (!form.start_date)         e.start_date = 'Start date required';
    if (!form.end_date)           e.end_date   = 'End date required';
    if (form.start_date && form.end_date && form.end_date < form.start_date)
      e.end_date = 'End date must be after start date';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
      {/* Name */}
      <div style={{ gridColumn: '1/-1' }}>
        <label style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b', display: 'block', marginBottom: '5px' }}>CIE Name *</label>
        <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. CIE-1 April 2026" style={inputSx} />
        {errors.name && <p style={{ fontSize: '0.68rem', color: '#EF4444', marginTop: '3px' }}>{errors.name}</p>}
      </div>
      {/* Start */}
      <div>
        <label style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b', display: 'block', marginBottom: '5px' }}>Start Date *</label>
        <input type="date" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} style={inputSx} />
        {errors.start_date && <p style={{ fontSize: '0.68rem', color: '#EF4444', marginTop: '3px' }}>{errors.start_date}</p>}
      </div>
      {/* End */}
      <div>
        <label style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b', display: 'block', marginBottom: '5px' }}>End Date *</label>
        <input type="date" value={form.end_date} onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))} style={inputSx} />
        {errors.end_date && <p style={{ fontSize: '0.68rem', color: '#EF4444', marginTop: '3px' }}>{errors.end_date}</p>}
      </div>
      {/* Description */}
      <div style={{ gridColumn: '1/-1' }}>
        <label style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b', display: 'block', marginBottom: '5px' }}>Description</label>
        <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={2} placeholder="Optional notes…" style={{ ...inputSx, resize: 'vertical', lineHeight: 1.5 }} />
      </div>
      {/* Active toggle */}
      <div style={{ gridColumn: '1/-1', display: 'flex', alignItems: 'center', gap: '10px' }}>
        <button
          type="button"
          onClick={() => setForm(f => ({ ...f, active_status: !f.active_status }))}
          style={{
            width: '40px', height: '22px', borderRadius: '99px', border: 'none', cursor: 'pointer', padding: '2px',
            background: form.active_status ? '#22C55E' : '#E2E8F0',
            display: 'flex', alignItems: 'center', transition: 'background 0.2s',
          }}
        >
          <span style={{
            width: '18px', height: '18px', borderRadius: '50%', background: '#fff',
            transform: form.active_status ? 'translateX(18px)' : 'translateX(0)',
            transition: 'transform 0.2s', display: 'block',
            boxShadow: '0 1px 4px rgba(0,0,0,0.2)',
          }} />
        </button>
        <span style={{ fontSize: '0.8rem', fontWeight: 600, color: form.active_status ? '#16A34A' : '#94a3b8' }}>
          {form.active_status ? 'Active' : 'Inactive'}
        </span>
      </div>
      {/* Buttons */}
      <div style={{ gridColumn: '1/-1', display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
        <button style={btnSecondary} onClick={onCancel}>Cancel</button>
        <button
          style={{ ...btnPrimary, opacity: saving ? 0.7 : 1, cursor: saving ? 'not-allowed' : 'pointer' }}
          onClick={() => { if (validate()) onSave(form); }}
          disabled={saving}
        >
          {saving ? <span style={{ width: '14px', height: '14px', border: '2px solid #fff4', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin .7s linear infinite', display: 'inline-block' }} /> : <Save size={14} />}
          Save CIE
        </button>
      </div>
    </div>
  );
}

export const CIEManagement: React.FC<CIEManagementProps> = ({
  records, loading = false, onCreate, onUpdate, onDelete, onRefresh,
}) => {
  const [showForm, setShowForm] = useState(false);
  const [editId,   setEditId]   = useState<string | null>(null);
  const [delId,    setDelId]    = useState<string | null>(null);
  const [saving,   setSaving]   = useState(false);
  const [search,   setSearch]   = useState('');

  const filtered = records.filter(r =>
    r.name.toLowerCase().includes(search.toLowerCase()) || r.cie_id.toLowerCase().includes(search.toLowerCase())
  );

  const handleCreate = async (data: Omit<CIERecord,'cie_id'>) => {
    if (!onCreate) return;
    setSaving(true);
    try { await onCreate(data); setShowForm(false); } finally { setSaving(false); }
  };

  const handleUpdate = async (data: Omit<CIERecord,'cie_id'>) => {
    if (!onUpdate || !editId) return;
    setSaving(true);
    try { await onUpdate(editId, data); setEditId(null); } finally { setSaving(false); }
  };

  const handleDelete = async (id: string) => {
    if (!onDelete) return;
    setSaving(true);
    try { await onDelete(id); setDelId(null); } finally { setSaving(false); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#1e293b', flex: 1 }}>CIE Management</h2>
        <div style={{ position: 'relative' }}>
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search CIEs…" style={{ ...inputSx, width: '200px', paddingLeft: '10px' }} />
        </div>
        {onRefresh && (
          <button style={btnSecondary} onClick={onRefresh}>
            <RefreshCw size={13} /> Refresh
          </button>
        )}
        {onCreate && (
          <button style={btnPrimary} onClick={() => { setShowForm(true); setEditId(null); }}>
            <Plus size={14} /> New CIE
          </button>
        )}
      </div>

      {/* Create form */}
      {showForm && !editId && (
        <div style={{ borderRadius: '16px', padding: '20px', background: '#F8FAFF', border: '1.5px solid #A5B4FC', animation: 'fadeIn .2s ease' }}>
          <p style={{ fontSize: '0.78rem', fontWeight: 700, color: '#6366F1', marginBottom: '14px' }}>Create New CIE</p>
          <CIEForm initial={EMPTY_CIE} onSave={handleCreate} onCancel={() => setShowForm(false)} saving={saving} />
        </div>
      )}

      {/* Table */}
      <div style={{ borderRadius: '14px', border: '1px solid #E2E8F0', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#F8FAFC', borderBottom: '2px solid #E2E8F0' }}>
              {['CIE ID','Name','Start Date','End Date','Status','Actions'].map(h => (
                <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94A3B8' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>Loading…</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={6} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>No CIE records found</td></tr>
            ) : filtered.map((r, i) => (
              <React.Fragment key={r.cie_id}>
                <tr style={{ borderBottom: '1px solid #F1F5F9', background: i % 2 === 0 ? '#fff' : '#FAFBFF' }}>
                  <td style={{ padding: '11px 14px', fontSize: '0.75rem', fontFamily: 'monospace', color: '#6366F1', fontWeight: 700 }}>{r.cie_id}</td>
                  <td style={{ padding: '11px 14px', fontSize: '0.82rem', fontWeight: 700, color: '#1e293b' }}>{r.name}</td>
                  <td style={{ padding: '11px 14px', fontSize: '0.78rem', color: '#64748b', fontFamily: 'monospace' }}>{r.start_date}</td>
                  <td style={{ padding: '11px 14px', fontSize: '0.78rem', color: '#64748b', fontFamily: 'monospace' }}>{r.end_date}</td>
                  <td style={{ padding: '11px 14px' }}>
                    <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '3px 10px', borderRadius: '99px', background: r.active_status ? '#F0FDF4' : '#F8FAFC', color: r.active_status ? '#16A34A' : '#94A3B8', border: `1px solid ${r.active_status ? '#BBF7D0' : '#E2E8F0'}` }}>
                      {r.active_status ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td style={{ padding: '11px 14px' }}>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      {onUpdate && (
                        <button style={{ ...btnSecondary, padding: '5px 10px', fontSize: '0.72rem' }} onClick={() => setEditId(r.cie_id)}>
                          <Edit2 size={12} /> Edit
                        </button>
                      )}
                      {onDelete && (
                        <button style={{ ...btnDanger, padding: '5px 10px', fontSize: '0.72rem' }} onClick={() => setDelId(r.cie_id)}>
                          <Trash2 size={12} /> Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
                {/* Inline edit row */}
                {editId === r.cie_id && (
                  <tr>
                    <td colSpan={6} style={{ padding: '16px 20px', background: '#F8FAFF', borderBottom: '2px solid #A5B4FC' }}>
                      <CIEForm
                        initial={r}
                        onSave={handleUpdate}
                        onCancel={() => setEditId(null)}
                        saving={saving}
                      />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Delete confirm modal */}
      {delId && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, backdropFilter: 'blur(3px)' }}>
          <div style={{ background: '#fff', borderRadius: '20px', padding: '28px 32px', maxWidth: '380px', width: '90%', boxShadow: '0 24px 60px rgba(0,0,0,0.18)' }}>
            <div style={{ width: '48px', height: '48px', borderRadius: '16px', background: '#FEF2F2', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
              <AlertTriangle size={24} style={{ color: '#EF4444' }} />
            </div>
            <p style={{ fontSize: '1rem', fontWeight: 800, color: '#1e293b', textAlign: 'center', marginBottom: '8px' }}>Delete CIE?</p>
            <p style={{ fontSize: '0.8rem', color: '#64748b', textAlign: 'center', marginBottom: '22px' }}>This will permanently remove the CIE record. This action cannot be undone.</p>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
              <button style={btnSecondary} onClick={() => setDelId(null)}>Cancel</button>
              <button style={{ ...btnPrimary, background: 'linear-gradient(135deg,#EF4444,#F87171)' }} onClick={() => handleDelete(delId)} disabled={saving}>
                {saving ? '…' : <><Trash2 size={14} /> Delete</>}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`@keyframes fadeIn{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:none}}@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
//  3. FileUploadForm
// ─────────────────────────────────────────────────────────────────────────────

export type UploadMode = 'timetable' | 'roster' | 'general';

interface CSVRow { [key: string]: string }

interface FileUploadFormProps {
  mode: UploadMode;
  title?: string;
  description?: string;
  expectedColumns?: string[];
  onUpload?: (rows: CSVRow[], raw: File) => Promise<{ success: number; failed: number; errors?: string[] }>;
  accept?: string;
}

function parseCSV(text: string): CSVRow[] {
  const lines  = text.split('\n').map(l => l.trim()).filter(Boolean);
  if (lines.length < 2) return [];
  const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''));
  return lines.slice(1).map(line => {
    const vals = line.split(',').map(v => v.trim().replace(/^"|"$/g, ''));
    const row: CSVRow = {};
    headers.forEach((h, i) => { row[h] = vals[i] ?? ''; });
    return row;
  });
}

export const FileUploadForm: React.FC<FileUploadFormProps> = ({
  mode, title, description, expectedColumns = [], onUpload, accept = '.csv',
}) => {
  const [file,       setFile]     = useState<File | null>(null);
  const [rows,       setRows]     = useState<CSVRow[]>([]);
  const [errors,     setErrors]   = useState<string[]>([]);
  const [uploading,  setUploading]= useState(false);
  const [result,     setResult]   = useState<{ success: number; failed: number; errors?: string[] } | null>(null);
  const [dragOver,   setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const modeConfig: Record<UploadMode, { icon: React.FC<any>; color: string; templateCols: string }> = {
    timetable: { icon: Calendar,     color: '#6366F1', templateCols: 'class_id,day_of_week,start_time,end_time,course_code,course_name,faculty_id' },
    roster:    { icon: Users,        color: '#8B5CF6', templateCols: 'student_id,name,email,roll_no,class_id' },
    general:   { icon: FileText,     color: '#14B8A6', templateCols: '' },
  };
  const cfg = modeConfig[mode];

  const processFile = (f: File) => {
    setFile(f); setResult(null); setErrors([]);
    const reader = new FileReader();
    reader.onload = e => {
      const text = e.target?.result as string;
      const parsed = parseCSV(text);
      setRows(parsed);
      // Validation
      if (parsed.length === 0) { setErrors(['File appears empty or incorrectly formatted.']); return; }
      const missing = expectedColumns.filter(col => !Object.keys(parsed[0]).includes(col));
      if (missing.length) setErrors([`Missing columns: ${missing.join(', ')}`]);
    };
    reader.readAsText(f);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) processFile(f);
  };

  const handleUpload = async () => {
    if (!file || !rows.length || !onUpload) return;
    setUploading(true);
    try {
      const res = await onUpload(rows, file);
      setResult(res);
    } finally {
      setUploading(false);
    }
  };

  const downloadTemplate = () => {
    const content = cfg.templateCols + '\n';
    const blob = new Blob([content], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${mode}_template.csv`;
    a.click();
  };

  const hasErrors = errors.length > 0;
  const colHeaders = rows.length > 0 ? Object.keys(rows[0]) : [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
      {/* Header */}
      <div>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#1e293b' }}>{title ?? `Upload ${mode.charAt(0).toUpperCase() + mode.slice(1)}`}</h2>
        {description && <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '4px' }}>{description}</p>}
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        style={{
          borderRadius: '16px', padding: '40px 20px', textAlign: 'center', cursor: 'pointer',
          border: `2px dashed ${dragOver ? cfg.color : '#CBD5E1'}`,
          background: dragOver ? `${cfg.color}08` : '#FAFBFF',
          transition: 'all 0.2s',
        }}
      >
        <input ref={inputRef} type="file" accept={accept} style={{ display: 'none' }}
          onChange={e => { const f = e.target.files?.[0]; if (f) processFile(f); }} />
        <div style={{ width: '52px', height: '52px', borderRadius: '16px', background: `${cfg.color}15`, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px' }}>
          <Upload size={24} style={{ color: cfg.color }} />
        </div>
        {file ? (
          <div>
            <p style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b' }}>{file.name}</p>
            <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '4px' }}>
              {rows.length} rows parsed · {(file.size / 1024).toFixed(1)} KB
            </p>
          </div>
        ) : (
          <div>
            <p style={{ fontSize: '0.9rem', fontWeight: 600, color: '#475569' }}>Drop your CSV here or click to browse</p>
            <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '6px' }}>Accepts {accept} files</p>
          </div>
        )}
      </div>

      {/* Validation errors */}
      {hasErrors && (
        <div style={{ padding: '12px 16px', borderRadius: '12px', background: '#FEF2F2', border: '1px solid #FECACA' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <AlertTriangle size={14} style={{ color: '#EF4444' }} />
            <p style={{ fontSize: '0.78rem', fontWeight: 700, color: '#DC2626' }}>Validation Issues</p>
          </div>
          {errors.map((e, i) => <p key={i} style={{ fontSize: '0.75rem', color: '#7F1D1D', paddingLeft: '22px' }}>• {e}</p>)}
        </div>
      )}

      {/* Preview table */}
      {rows.length > 0 && !hasErrors && (
        <div>
          <p style={{ fontSize: '0.7rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>
            Preview — first {Math.min(5, rows.length)} of {rows.length} rows
          </p>
          <div style={{ borderRadius: '12px', border: '1px solid #E2E8F0', overflow: 'auto', maxHeight: '220px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
              <thead>
                <tr style={{ background: '#F8FAFC', borderBottom: '2px solid #E2E8F0' }}>
                  {colHeaders.map(h => (
                    <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 700, color: '#64748b', whiteSpace: 'nowrap' }}>
                      {h}
                      {expectedColumns.includes(h) && <span style={{ marginLeft: '4px', color: '#22C55E' }}>✓</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 5).map((row, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #F1F5F9', background: i % 2 === 0 ? '#fff' : '#FAFBFF' }}>
                    {colHeaders.map(h => (
                      <td key={h} style={{ padding: '7px 12px', color: '#475569', whiteSpace: 'nowrap', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {row[h] || <span style={{ color: '#CBD5E1' }}>—</span>}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Result banner */}
      {result && (
        <div style={{
          padding: '14px 18px', borderRadius: '14px', animation: 'fadeIn .2s ease',
          background: result.failed === 0 ? '#F0FDF4' : '#FFFBEB',
          border: `1px solid ${result.failed === 0 ? '#BBF7D0' : '#FDE68A'}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
            {result.failed === 0
              ? <CheckCircle size={16} style={{ color: '#22C55E' }} />
              : <AlertTriangle size={16} style={{ color: '#F59E0B' }} />}
            <p style={{ fontSize: '0.85rem', fontWeight: 700, color: result.failed === 0 ? '#166534' : '#92400E' }}>
              {result.success} imported successfully{result.failed > 0 ? `, ${result.failed} failed` : ''}
            </p>
          </div>
          {result.errors?.map((e, i) => <p key={i} style={{ fontSize: '0.72rem', color: '#B45309', paddingLeft: '26px' }}>• {e}</p>)}
        </div>
      )}

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: '10px', justifyContent: 'space-between', flexWrap: 'wrap' }}>
        {cfg.templateCols && (
          <button style={btnSecondary} onClick={downloadTemplate}>
            <Download size={13} /> Download Template
          </button>
        )}
        <div style={{ display: 'flex', gap: '10px' }}>
          {file && (
            <button style={btnSecondary} onClick={() => { setFile(null); setRows([]); setErrors([]); setResult(null); }}>
              <X size={13} /> Clear
            </button>
          )}
          {onUpload && (
            <button
              style={{ ...btnPrimary, opacity: (!file || hasErrors || uploading) ? 0.6 : 1, cursor: (!file || hasErrors || uploading) ? 'not-allowed' : 'pointer' }}
              onClick={handleUpload}
              disabled={!file || hasErrors || uploading}
            >
              {uploading
                ? <span style={{ width: '14px', height: '14px', border: '2px solid #fff4', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin .7s linear infinite', display: 'inline-block' }} />
                : <Upload size={14} />}
              {uploading ? 'Uploading…' : `Upload ${rows.length > 0 ? `(${rows.length} rows)` : ''}`}
            </button>
          )}
        </div>
      </div>
      <style>{`@keyframes fadeIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
//  4. ReportsPage
// ─────────────────────────────────────────────────────────────────────────────

export interface ReportData {
  daily_trend: Array<{ date: string; present: number; absent: number; late: number }>;
  course_summary: Array<{ course: string; percentage: number; color: string }>;
  weekly_avg: Array<{ week: string; avg: number }>;
  summary: {
    total_sessions: number;
    avg_attendance: number;
    highest_course: string;
    lowest_course: string;
    critical_count: number;
  };
}

interface ReportsPageProps {
  data: ReportData;
  loading?: boolean;
  onExport?: () => void;
  onRefresh?: () => void;
}

const CHART_COLORS = ['#6366F1','#22C55E','#F59E0B','#EF4444','#8B5CF6','#14B8A6','#F97316','#EC4899'];

export const ReportsPage: React.FC<ReportsPageProps> = ({
  data, loading = false, onExport, onRefresh,
}) => {
  const [chartType, setChartType] = useState<'bar' | 'line'>('bar');
  const { daily_trend, course_summary, weekly_avg, summary } = data;

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    return (
      <div style={{ background: '#1e293b', borderRadius: '10px', padding: '10px 14px', boxShadow: '0 8px 24px rgba(0,0,0,0.2)' }}>
        <p style={{ fontSize: '0.72rem', color: '#94a3b8', marginBottom: '6px' }}>{label}</p>
        {payload.map((p: any) => (
          <div key={p.dataKey} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: p.fill || p.stroke }} />
            <span style={{ fontSize: '0.78rem', color: '#e2e8f0', fontWeight: 600, textTransform: 'capitalize' }}>{p.dataKey}: {p.value}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 900, color: '#1e293b' }}>Attendance Reports</h2>
          <p style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '3px' }}>Overview of attendance across classes and courses</p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {onRefresh && <button style={btnSecondary} onClick={onRefresh}><RefreshCw size={13} />Refresh</button>}
          {onExport  && <button style={btnPrimary}    onClick={onExport}><Download size={13} />Export</button>}
        </div>
      </div>

      {/* Summary KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: '10px' }}>
        {[
          { label: 'Total Sessions',   val: summary.total_sessions,              hex: '#6366F1' },
          { label: 'Avg Attendance',   val: `${summary.avg_attendance.toFixed(1)}%`, hex: summary.avg_attendance >= 75 ? '#22C55E' : '#EF4444' },
          { label: 'Best Course',      val: summary.highest_course,              hex: '#22C55E' },
          { label: 'Weakest Course',   val: summary.lowest_course,               hex: '#F59E0B' },
          { label: 'Critical Students',val: summary.critical_count,              hex: '#EF4444' },
        ].map(({ label, val, hex }) => (
          <div key={label} style={{ padding: '14px 16px', borderRadius: '14px', background: `${hex}0a`, border: `1.5px solid ${hex}25` }}>
            <p style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '5px' }}>{label}</p>
            <p style={{ fontSize: typeof val === 'string' && val.length > 6 ? '0.8rem' : '1.3rem', fontWeight: 900, color: hex, lineHeight: 1 }}>{val}</p>
          </div>
        ))}
      </div>

      {/* Daily trend chart */}
      <div style={{ borderRadius: '18px', border: '1px solid #E2E8F0', padding: '20px 24px', background: '#fff' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#1e293b' }}>Daily Attendance Trend</h3>
          <div style={{ display: 'flex', gap: '6px' }}>
            {(['bar', 'line'] as const).map(t => (
              <button key={t} onClick={() => setChartType(t)} style={{
                padding: '5px 12px', borderRadius: '8px', fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer',
                background: chartType === t ? '#6366F1' : '#F1F5F9',
                color: chartType === t ? '#fff' : '#64748b',
                border: `1px solid ${chartType === t ? '#6366F1' : '#E2E8F0'}`,
              }}>
                {t === 'bar' ? <BarChart2 size={12} style={{ display: 'inline', marginRight: '4px' }} /> : <Activity size={12} style={{ display: 'inline', marginRight: '4px' }} />}
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <ResponsiveContainer width="100%" height={220}>
          {chartType === 'bar' ? (
            <BarChart data={daily_trend} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94A3B8' }} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#94A3B8' }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: '0.72rem', marginTop: '8px' }} />
              <Bar dataKey="present" fill="#22C55E" radius={[4,4,0,0]} maxBarSize={28} />
              <Bar dataKey="late"    fill="#F59E0B" radius={[4,4,0,0]} maxBarSize={28} />
              <Bar dataKey="absent"  fill="#EF4444" radius={[4,4,0,0]} maxBarSize={28} />
            </BarChart>
          ) : (
            <LineChart data={daily_trend} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94A3B8' }} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#94A3B8' }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: '0.72rem', marginTop: '8px' }} />
              <Line type="monotone" dataKey="present" stroke="#22C55E" strokeWidth={2.5} dot={false} />
              <Line type="monotone" dataKey="late"    stroke="#F59E0B" strokeWidth={2.5} dot={false} />
              <Line type="monotone" dataKey="absent"  stroke="#EF4444" strokeWidth={2.5} dot={false} />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>

      {/* Two-column: pie + weekly avg */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: '16px' }}>

        {/* Course breakdown pie */}
        <div style={{ borderRadius: '18px', border: '1px solid #E2E8F0', padding: '20px 24px', background: '#fff' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#1e293b', marginBottom: '16px' }}>Course Attendance %</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={course_summary} dataKey="percentage" nameKey="course" cx="50%" cy="50%" outerRadius={75} innerRadius={38} paddingAngle={3}>
                {course_summary.map((entry, i) => (
                  <Cell key={entry.course} fill={entry.color || CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(val: number) => [`${val.toFixed(1)}%`, 'Attendance']} />
              <Legend wrapperStyle={{ fontSize: '0.7rem' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Weekly average line */}
        <div style={{ borderRadius: '18px', border: '1px solid #E2E8F0', padding: '20px 24px', background: '#fff' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#1e293b', marginBottom: '16px' }}>Weekly Average</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={weekly_avg} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
              <XAxis dataKey="week" tick={{ fontSize: 10, fill: '#94A3B8' }} tickLine={false} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#94A3B8' }} tickLine={false} axisLine={false} unit="%" />
              <Tooltip formatter={(val: number) => [`${val.toFixed(1)}%`, 'Avg Attendance']} />
              {/* 75% reference line */}
              <Line type="monotone" dataKey="avg" stroke="#6366F1" strokeWidth={2.5} dot={{ fill: '#6366F1', r: 4 }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #F1F5F9' }}>
            <span style={{ width: '20px', height: '2px', background: '#F59E0B', display: 'inline-block' }} />
            <span style={{ fontSize: '0.68rem', color: '#94a3b8' }}>75% attendance threshold</span>
          </div>
        </div>
      </div>

      {/* Course-level breakdown table */}
      <div style={{ borderRadius: '18px', border: '1px solid #E2E8F0', padding: '20px 24px', background: '#fff' }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#1e293b', marginBottom: '16px' }}>Course-Level Breakdown</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {[...course_summary].sort((a, b) => a.percentage - b.percentage).map((c, i) => {
            const band = c.percentage >= 85 ? '#22C55E' : c.percentage >= 75 ? '#F59E0B' : '#EF4444';
            return (
              <div key={c.course} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 14px', borderRadius: '12px', background: i % 2 === 0 ? '#F8FAFF' : '#fff', border: '1px solid #F1F5F9' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: c.color || CHART_COLORS[i % CHART_COLORS.length], flexShrink: 0 }} />
                <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#1e293b', flex: 1 }}>{c.course}</span>
                <div style={{ width: '120px' }}>
                  <div style={{ height: '6px', borderRadius: '99px', background: '#E2E8F0', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${Math.min(100, c.percentage)}%`, background: band, borderRadius: '99px' }} />
                  </div>
                </div>
                <span style={{ fontSize: '0.8rem', fontWeight: 800, color: band, minWidth: '44px', textAlign: 'right', fontFamily: 'monospace' }}>
                  {c.percentage.toFixed(1)}%
                </span>
                {c.percentage < 75 && (
                  <AlertTriangle size={14} style={{ color: '#EF4444' }} />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
