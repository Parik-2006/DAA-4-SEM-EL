/**
 * AttendanceSheet.tsx
 *
 * Teacher-facing attendance roster with:
 *  - Student roll_no / name / photo
 *  - Status dropdown per student (present/absent/late)
 *  - Quick icon buttons for rapid marking
 *  - Bulk "Mark All Present/Absent" with undo
 *  - Before-lock editing indicator
 *  - Submit / save session
 */

import React, { useState, useCallback, useRef } from 'react';
import {
  CheckCircle, XCircle, Clock, RotateCcw, ChevronDown,
  Users, Check, Save, Undo2, Lock, Unlock, Search, AlertTriangle
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────────

export type AttendanceStatus = 'present' | 'absent' | 'late' | 'not_marked';

export interface RosterStudent {
  student_id: string;
  roll_no: string;
  name: string;
  photo_url?: string;
  class_id: string;
}

export interface AttendanceEntry {
  student_id: string;
  status: AttendanceStatus;
  notes?: string;
}

interface AttendanceSheetProps {
  periodId: string;
  periodLabel: string;        // e.g. "CS401 — Machine Learning (09:00–10:00)"
  students: RosterStudent[];
  initialEntries?: Record<string, AttendanceStatus>;
  isLocked?: boolean;
  onSave?: (entries: AttendanceEntry[]) => Promise<void>;
}

// ── Constants ──────────────────────────────────────────────────────────────────

const STATUS_CFG: Record<AttendanceStatus, { label: string; hex: string; bg: string; icon: React.FC<any> }> = {
  present:    { label: 'Present',    hex: '#22C55E', bg: '#F0FDF4', icon: CheckCircle },
  absent:     { label: 'Absent',     hex: '#EF4444', bg: '#FEF2F2', icon: XCircle },
  late:       { label: 'Late',       hex: '#F59E0B', bg: '#FFFBEB', icon: Clock },
  not_marked: { label: 'Not Marked', hex: '#94A3B8', bg: '#F8FAFC', icon: RotateCcw },
};

// ── Student row ────────────────────────────────────────────────────────────────

interface StudentRowProps {
  student: RosterStudent;
  status: AttendanceStatus;
  isLocked: boolean;
  onChange: (id: string, s: AttendanceStatus) => void;
  index: number;
}

function StudentRow({ student, status, isLocked, onChange, index }: StudentRowProps) {
  const cfg = STATUS_CFG[status];
  const Icon = cfg.icon;
  const [showDropdown, setShowDropdown] = useState(false);
  const dropRef = useRef<HTMLDivElement>(null);

  const handleOutside = useCallback((e: MouseEvent) => {
    if (dropRef.current && !dropRef.current.contains(e.target as Node)) {
      setShowDropdown(false);
    }
  }, []);

  React.useEffect(() => {
    if (showDropdown) document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, [showDropdown, handleOutside]);

  const initials = student.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();

  return (
    <tr
      style={{
        borderBottom: '1px solid #f1f5f9',
        background: index % 2 === 0 ? '#fff' : '#fafbff',
        transition: 'background 0.15s',
      }}
      onMouseEnter={e => { if (!isLocked) (e.currentTarget as HTMLElement).style.background = '#f1f5f9'; }}
      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = index % 2 === 0 ? '#fff' : '#fafbff'; }}
    >
      {/* Roll no */}
      <td style={{ padding: '10px 14px', fontSize: '0.8rem', fontFamily: 'monospace', fontWeight: 600, color: '#6366F1', whiteSpace: 'nowrap', width: '80px' }}>
        {student.roll_no}
      </td>

      {/* Name + photo */}
      <td style={{ padding: '10px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {student.photo_url ? (
            <img src={student.photo_url} alt={student.name}
              style={{ width: '34px', height: '34px', borderRadius: '50%', objectFit: 'cover', border: '2px solid #e2e8f0', flexShrink: 0 }} />
          ) : (
            <div style={{
              width: '34px', height: '34px', borderRadius: '50%', flexShrink: 0,
              background: `linear-gradient(135deg, #6366F122 0%, #8B5CF622 100%)`,
              border: '2px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '0.65rem', fontWeight: 800, color: '#6366F1',
            }}>
              {initials}
            </div>
          )}
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#1e293b' }}>{student.name}</span>
        </div>
      </td>

      {/* Quick action buttons */}
      <td style={{ padding: '10px 14px', whiteSpace: 'nowrap' }}>
        {!isLocked && (
          <div style={{ display: 'flex', gap: '6px' }}>
            {(['present', 'late', 'absent'] as AttendanceStatus[]).map(s => {
              const c = STATUS_CFG[s];
              const SIcon = c.icon;
              const active = status === s;
              return (
                <button
                  key={s}
                  onClick={() => onChange(student.student_id, active ? 'not_marked' : s)}
                  title={c.label}
                  style={{
                    width: '30px', height: '30px', borderRadius: '8px', cursor: 'pointer',
                    border: `1.5px solid ${active ? c.hex : '#e2e8f0'}`,
                    background: active ? c.bg : '#fff',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={e => { if (!active) { (e.currentTarget as HTMLElement).style.background = c.bg; (e.currentTarget as HTMLElement).style.borderColor = c.hex; } }}
                  onMouseLeave={e => { if (!active) { (e.currentTarget as HTMLElement).style.background = '#fff'; (e.currentTarget as HTMLElement).style.borderColor = '#e2e8f0'; } }}
                >
                  <SIcon size={14} style={{ color: active ? c.hex : '#94a3b8' }} />
                </button>
              );
            })}
          </div>
        )}
      </td>

      {/* Status badge + dropdown */}
      <td style={{ padding: '10px 14px' }}>
        <div style={{ position: 'relative' }} ref={dropRef}>
          <button
            onClick={() => !isLocked && setShowDropdown(!showDropdown)}
            disabled={isLocked}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px', padding: '5px 10px 5px 8px',
              borderRadius: '99px', cursor: isLocked ? 'not-allowed' : 'pointer',
              background: cfg.bg, border: `1.5px solid ${cfg.hex}40`,
              opacity: isLocked ? 0.8 : 1,
            }}
          >
            <Icon size={13} style={{ color: cfg.hex }} />
            <span style={{ fontSize: '0.72rem', fontWeight: 700, color: cfg.hex }}>{cfg.label}</span>
            {!isLocked && <ChevronDown size={11} style={{ color: cfg.hex }} />}
          </button>

          {showDropdown && (
            <div style={{
              position: 'absolute', top: '100%', left: 0, zIndex: 50, marginTop: '4px',
              background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0',
              boxShadow: '0 8px 24px rgba(0,0,0,0.12)', minWidth: '140px', overflow: 'hidden',
              animation: 'fadeIn 0.15s ease',
            }}>
              {(Object.keys(STATUS_CFG) as AttendanceStatus[]).map(s => {
                const c = STATUS_CFG[s];
                const DIcon = c.icon;
                return (
                  <button
                    key={s}
                    onClick={() => { onChange(student.student_id, s); setShowDropdown(false); }}
                    style={{
                      width: '100%', display: 'flex', alignItems: 'center', gap: '8px',
                      padding: '8px 12px', border: 'none', background: 'transparent', cursor: 'pointer',
                      fontSize: '0.78rem', fontWeight: status === s ? 700 : 500,
                      color: status === s ? c.hex : '#475569',
                      borderLeft: status === s ? `3px solid ${c.hex}` : '3px solid transparent',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = c.bg)}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    <DIcon size={13} style={{ color: c.hex }} />
                    {c.label}
                    {status === s && <Check size={11} style={{ marginLeft: 'auto', color: c.hex }} />}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export const AttendanceSheet: React.FC<AttendanceSheetProps> = ({
  periodId,
  periodLabel,
  students,
  initialEntries = {},
  isLocked: initialLocked = false,
  onSave,
}) => {
  const [entries, setEntries] = useState<Record<string, AttendanceStatus>>(() => {
    const base: Record<string, AttendanceStatus> = {};
    students.forEach(s => { base[s.student_id] = initialEntries[s.student_id] ?? 'not_marked'; });
    return base;
  });
  const [undoStack, setUndoStack] = useState<Array<Record<string, AttendanceStatus>>>([]);
  const [isLocked, setIsLocked] = useState(initialLocked);
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [search, setSearch] = useState('');

  const pushUndo = useCallback((prev: Record<string, AttendanceStatus>) => {
    setUndoStack(s => [...s.slice(-9), prev]);
  }, []);

  const change = useCallback((id: string, status: AttendanceStatus) => {
    setEntries(prev => {
      pushUndo(prev);
      return { ...prev, [id]: status };
    });
    setSaved(false);
  }, [pushUndo]);

  const markAll = useCallback((status: 'present' | 'absent') => {
    setEntries(prev => {
      pushUndo(prev);
      const next = { ...prev };
      students.forEach(s => { next[s.student_id] = status; });
      return next;
    });
    setSaved(false);
  }, [students, pushUndo]);

  const undo = useCallback(() => {
    if (!undoStack.length) return;
    const last = undoStack[undoStack.length - 1];
    setUndoStack(s => s.slice(0, -1));
    setEntries(last);
    setSaved(false);
  }, [undoStack]);

  const handleSave = async () => {
    if (!onSave) return;
    setIsSaving(true);
    try {
      const result: AttendanceEntry[] = students.map(s => ({ student_id: s.student_id, status: entries[s.student_id] ?? 'not_marked' }));
      await onSave(result);
      setSaved(true);
      setIsLocked(true);
    } catch {
      // error handled by parent
    } finally {
      setIsSaving(false);
    }
  };

  const counts = { present: 0, absent: 0, late: 0, not_marked: 0 };
  Object.values(entries).forEach(s => { counts[s]++; });

  const filtered = students.filter(s =>
    !search || s.name.toLowerCase().includes(search.toLowerCase()) || s.roll_no.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8' }}>Attendance Sheet</span>
            {isLocked ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.65rem', padding: '2px 8px', borderRadius: '99px', background: '#FEF3C7', color: '#92400E', fontWeight: 700 }}>
                <Lock size={10} /> Locked
              </span>
            ) : (
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.65rem', padding: '2px 8px', borderRadius: '99px', background: '#F0FDF4', color: '#166534', fontWeight: 700 }}>
                <Unlock size={10} /> Editable
              </span>
            )}
          </div>
          <h2 style={{ fontSize: '1rem', fontWeight: 800, color: '#1e293b', lineHeight: 1.3 }}>{periodLabel}</h2>
        </div>

        {/* Stat pills */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {(Object.keys(counts) as AttendanceStatus[]).map(s => {
            const cfg = STATUS_CFG[s];
            return (
              <div key={s} style={{ padding: '4px 10px', borderRadius: '99px', background: cfg.bg, border: `1px solid ${cfg.hex}30` }}>
                <span style={{ fontSize: '0.72rem', fontWeight: 700, color: cfg.hex }}>{counts[s]} {cfg.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
        {/* Search */}
        <div style={{ position: 'relative', flex: 1, minWidth: '180px' }}>
          <Search size={13} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name or roll no…"
            style={{ width: '100%', paddingLeft: '30px', padding: '7px 12px 7px 30px', borderRadius: '10px', border: '1.5px solid #e2e8f0', fontSize: '0.8rem', background: '#fff', color: '#1e293b', outline: 'none' }}
          />
        </div>

        {!isLocked && (
          <>
            <button
              onClick={() => markAll('present')}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '7px 12px', borderRadius: '10px', border: '1.5px solid #BBF7D0', background: '#F0FDF4', color: '#166534', fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer' }}
            >
              <Users size={13} /> All Present
            </button>
            <button
              onClick={() => markAll('absent')}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '7px 12px', borderRadius: '10px', border: '1.5px solid #FECACA', background: '#FEF2F2', color: '#DC2626', fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer' }}
            >
              <XCircle size={13} /> All Absent
            </button>
            <button
              onClick={undo}
              disabled={!undoStack.length}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '7px 12px', borderRadius: '10px', border: '1.5px solid #e2e8f0', background: '#f8fafc', color: '#64748b', fontSize: '0.78rem', fontWeight: 600, cursor: undoStack.length ? 'pointer' : 'not-allowed', opacity: undoStack.length ? 1 : 0.4 }}
            >
              <Undo2 size={13} /> Undo
            </button>
          </>
        )}

        {isLocked && (
          <button
            onClick={() => setIsLocked(false)}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '7px 12px', borderRadius: '10px', border: '1.5px solid #FED7AA', background: '#FFF7ED', color: '#C2410C', fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer' }}
          >
            <Unlock size={13} /> Unlock for Editing
          </button>
        )}
      </div>

      {/* Not-marked warning */}
      {counts.not_marked > 0 && !isLocked && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 14px', borderRadius: '10px', background: '#FFFBEB', border: '1px solid #FDE68A' }}>
          <AlertTriangle size={14} style={{ color: '#F59E0B' }} />
          <p style={{ fontSize: '0.78rem', color: '#92400E', fontWeight: 500 }}>
            <strong>{counts.not_marked}</strong> student{counts.not_marked > 1 ? 's' : ''} not yet marked
          </p>
        </div>
      )}

      {/* Table */}
      <div style={{ borderRadius: '14px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0' }}>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8', width: '80px' }}>Roll No</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8' }}>Student</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8', width: '130px' }}>Quick Mark</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8', width: '160px' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s, i) => (
              <StudentRow key={s.student_id} student={s} status={entries[s.student_id] ?? 'not_marked'} isLocked={isLocked} onChange={change} index={i} />
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={4} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>
                  No students match your search
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Save button */}
      {!isLocked && onSave && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '12px' }}>
          {saved && (
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', color: '#22C55E', fontWeight: 600 }}>
              <CheckCircle size={14} /> Saved successfully
            </span>
          )}
          <button
            onClick={handleSave}
            disabled={isSaving}
            style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '10px 24px', borderRadius: '12px', fontSize: '0.85rem', fontWeight: 700, cursor: isSaving ? 'not-allowed' : 'pointer',
              background: isSaving ? '#A5B4FC' : 'linear-gradient(135deg, #6366F1 0%, #818CF8 100%)',
              color: '#fff', border: 'none', boxShadow: isSaving ? 'none' : '0 4px 14px #6366F140',
            }}
          >
            {isSaving ? (
              <div style={{ width: '16px', height: '16px', border: '2px solid #fff4', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
            ) : <Save size={15} />}
            {isSaving ? 'Saving…' : 'Save & Lock Session'}
          </button>
        </div>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: none; } }
      `}</style>
    </div>
  );
};

export default AttendanceSheet;
