import React from 'react';
import { AttendanceRecord } from '@/services/api';
import { Badge } from './UI';
import { Check, Clock, X, FileText } from 'lucide-react';

/* ── Status config ─────────────────────────────────────────────────────────── */
const statusConfig = {
  present: {
    icon: <Check size={14} />,
    label: 'Present',
    variant: 'success' as const,
    accent: 'var(--sage)',
    accentBg: 'rgba(107,138,113,0.10)',
    avatarRing: 'rgba(107,138,113,0.35)',
  },
  late: {
    icon: <Clock size={14} />,
    label: 'Late',
    variant: 'warning' as const,
    accent: '#9B7030',
    accentBg: 'rgba(176,128,48,0.10)',
    avatarRing: 'rgba(176,128,48,0.35)',
  },
  absent: {
    icon: <X size={14} />,
    label: 'Absent',
    variant: 'danger' as const,
    accent: 'var(--terra)',
    accentBg: 'rgba(193,123,91,0.10)',
    avatarRing: 'rgba(193,123,91,0.35)',
  },
  excused: {
    icon: <FileText size={14} />,
    label: 'Excused',
    variant: 'info' as const,
    accent: '#5A72A0',
    accentBg: 'rgba(106,130,168,0.10)',
    avatarRing: 'rgba(106,130,168,0.35)',
  },
};

const getRelativeTime = (date: Date): string => {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
};

/* ── AttendanceRecordCard ─────────────────────────────────────────────────── */
interface AttendanceRecordCardProps {
  record: AttendanceRecord;
}

export const AttendanceRecordCard: React.FC<AttendanceRecordCardProps> = ({ record }) => {
  const cfg = statusConfig[record.status as keyof typeof statusConfig] ?? statusConfig.present;
  const markedTime = new Date(record.marked_at);
  const relativeTime = getRelativeTime(markedTime);

  const [hovered, setHovered] = React.useState(false);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="shimmer-hover animate-fade-in-up"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '14px',
        padding: '12px 14px',
        borderRadius: '14px',
        background: hovered ? 'var(--glass-bg-hover)' : 'var(--glass-bg)',
        backdropFilter: 'var(--blur-sm)',
        WebkitBackdropFilter: 'var(--blur-sm)',
        border: `1px solid ${hovered ? 'var(--glass-border-hover)' : 'var(--glass-border)'}`,
        boxShadow: hovered ? '0 6px 24px rgba(80,50,20,0.09)' : '0 2px 8px rgba(80,50,20,0.04)',
        transition: 'all 0.25s ease',
        transform: hovered ? 'translateY(-1px)' : 'translateY(0)',
        cursor: 'default',
      }}
    >
      {/* Avatar */}
      <div
        style={{
          width: '40px',
          height: '40px',
          borderRadius: '50%',
          flexShrink: 0,
          border: `2px solid ${cfg.avatarRing}`,
          overflow: 'hidden',
          boxShadow: `0 0 0 3px ${cfg.accentBg}`,
        }}
      >
        {record.avatar_url ? (
          <img src={record.avatar_url} alt={record.student_name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <div
            style={{
              width: '100%',
              height: '100%',
              background: `linear-gradient(135deg, var(--cream-300) 0%, var(--cream-400) 100%)`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--gold)',
              fontSize: '14px',
              fontWeight: 700,
              fontFamily: 'Fraunces, serif',
            }}
          >
            {record.student_name.charAt(0).toUpperCase()}
          </div>
        )}
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '2px' }}>
          <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--ink)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {record.student_name}
          </span>
          <span style={{ fontSize: '0.7rem', color: 'var(--whisper)', fontFamily: 'DM Mono, monospace', flexShrink: 0 }}>
            {record.student_id}
          </span>
        </div>
        <span style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>{record.course_name}</span>
      </div>

      {/* Meta */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px', flexShrink: 0 }}>
        <Badge variant={cfg.variant} size="sm">{cfg.label}</Badge>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ fontSize: '0.65rem', color: 'var(--whisper)' }}>{relativeTime}</span>
          {record.confidence != null && (
            <span
              style={{
                fontSize: '0.65rem',
                color: 'var(--whisper)',
                background: 'rgba(155,122,58,0.08)',
                padding: '1px 5px',
                borderRadius: '99px',
                fontFamily: 'DM Mono, monospace',
              }}
            >
              {(record.confidence * 100).toFixed(0)}%
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

/* ── Table ─────────────────────────────────────────────────────────────────── */
interface TableColumn<T> {
  key: keyof T;
  label: string;
  render?: (value: any, row: T) => React.ReactNode;
  width?: string;
}

interface TableProps<T> {
  data: T[];
  columns: TableColumn<T>[];
  isLoading?: boolean;
  emptyMessage?: string;
}

export function Table<T>({ data, columns, isLoading = false, emptyMessage = 'No data available' }: TableProps<T>) {
  if (isLoading) {
    return (
      <div style={{ padding: '3rem 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
        {[...Array(4)].map((_, i) => (
          <div
            key={i}
            className="skeleton-cream"
            style={{ width: '100%', height: '48px', animationDelay: `${i * 80}ms` }}
          />
        ))}
        <p style={{ fontSize: '0.8rem', color: 'var(--whisper)', marginTop: '4px' }}>Loading records…</p>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div style={{ padding: '4rem 0', textAlign: 'center' }}>
        <div
          style={{
            width: '52px',
            height: '52px',
            borderRadius: '16px',
            background: 'rgba(155,122,58,0.08)',
            border: '1px solid rgba(155,122,58,0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 14px',
          }}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--whisper)" strokeWidth="1.5">
            <rect x="3" y="3" width="18" height="18" rx="3" />
            <path d="M3 9h18" />
            <path d="M9 21V9" />
          </svg>
        </div>
        <p style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--muted)' }}>{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: '0 4px' }}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={String(col.key)}
                className={col.width || ''}
                style={{
                  padding: '8px 16px',
                  textAlign: 'left',
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  letterSpacing: '0.10em',
                  textTransform: 'uppercase',
                  color: 'var(--whisper)',
                  borderBottom: '1px solid rgba(190,160,118,0.20)',
                  whiteSpace: 'nowrap',
                }}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="stagger-children">
          {data.map((row, rowIndex) => (
            <TableRow key={rowIndex} row={row} columns={columns} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TableRow<T>({ row, columns }: { row: T; columns: TableColumn<T>[] }) {
  const [hovered, setHovered] = React.useState(false);
  return (
    <tr
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="animate-fade-in"
      style={{ transition: 'all 0.18s ease' }}
    >
      {columns.map((col, colIdx) => (
        <td
          key={String(col.key)}
          style={{
            padding: '10px 16px',
            fontSize: '0.8125rem',
            color: 'var(--ink)',
            background: hovered ? 'rgba(254,252,248,0.85)' : 'rgba(254,252,248,0.55)',
            borderTop: `1px solid ${hovered ? 'rgba(190,160,118,0.20)' : 'rgba(190,160,118,0.10)'}`,
            borderBottom: `1px solid ${hovered ? 'rgba(190,160,118,0.20)' : 'rgba(190,160,118,0.10)'}`,
            borderLeft: colIdx === 0 ? `1px solid ${hovered ? 'rgba(190,160,118,0.20)' : 'rgba(190,160,118,0.10)'}` : 'none',
            borderRight: colIdx === columns.length - 1 ? `1px solid ${hovered ? 'rgba(190,160,118,0.20)' : 'rgba(190,160,118,0.10)'}` : 'none',
            borderRadius: colIdx === 0 ? '10px 0 0 10px' : colIdx === columns.length - 1 ? '0 10px 10px 0' : '0',
            transition: 'background 0.18s ease, border-color 0.18s ease',
          }}
        >
          {col.render ? col.render(row[col.key], row) : String(row[col.key] ?? '')}
        </td>
      ))}
    </tr>
  );
}
