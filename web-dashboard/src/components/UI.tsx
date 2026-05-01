import React from 'react';

/* ── Card ─────────────────────────────────────────────────────────────────── */
interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export const Card: React.FC<CardProps> = ({ children, className = '', onClick }) => (
  <div
    onClick={onClick}
    className={`glass rounded-2xl p-6 animate-fade-in-up ${onClick ? 'glass-lift cursor-pointer' : ''} ${className}`}
    style={{ position: 'relative', overflow: 'hidden' }}
  >
    {/* Subtle grain texture overlay */}
    <div
      aria-hidden
      style={{
        position: 'absolute',
        inset: 0,
        backgroundImage:
          "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='200' height='200' filter='url(%23n)' opacity='0.018'/%3E%3C/svg%3E\")",
        pointerEvents: 'none',
        borderRadius: 'inherit',
        zIndex: 0,
      }}
    />
    <div style={{ position: 'relative', zIndex: 1 }}>{children}</div>
  </div>
);

/* ── StatCard ─────────────────────────────────────────────────────────────── */
interface StatCardProps {
  label: string;
  value: string | number;
  color: 'primary' | 'success' | 'warning' | 'danger' | 'info';
  icon?: React.ReactNode;
  trend?: { value: number; isPositive: boolean };
}

const statColorMap = {
  primary: {
    accent: 'var(--gold)',
    accentBg: 'rgba(155,122,58,0.10)',
    bar: 'linear-gradient(90deg, var(--gold-light), var(--gold))',
    text: 'var(--gold)',
    border: 'rgba(155,122,58,0.18)',
  },
  success: {
    accent: 'var(--sage)',
    accentBg: 'rgba(107,138,113,0.10)',
    bar: 'linear-gradient(90deg, #A8C4AD, var(--sage))',
    text: 'var(--sage)',
    border: 'rgba(107,138,113,0.18)',
  },
  warning: {
    accent: '#B08030',
    accentBg: 'rgba(176,128,48,0.10)',
    bar: 'linear-gradient(90deg, #D4A84A, #B08030)',
    text: '#B08030',
    border: 'rgba(176,128,48,0.18)',
  },
  danger: {
    accent: 'var(--terra)',
    accentBg: 'rgba(193,123,91,0.10)',
    bar: 'linear-gradient(90deg, #D4987A, var(--terra))',
    text: 'var(--terra)',
    border: 'rgba(193,123,91,0.18)',
  },
  info: {
    accent: '#6A82A8',
    accentBg: 'rgba(106,130,168,0.10)',
    bar: 'linear-gradient(90deg, #8BA4C4, #6A82A8)',
    text: '#6A82A8',
    border: 'rgba(106,130,168,0.18)',
  },
};

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  color,
  icon,
  trend,
}) => {
  const c = statColorMap[color];
  return (
    <div
      className="glass rounded-2xl glass-lift animate-fade-in-up"
      style={{
        position: 'relative',
        overflow: 'hidden',
        border: `1px solid ${c.border}`,
      }}
    >
      {/* Top accent bar */}
      <div style={{ height: '3px', background: c.bar, borderRadius: '8px 8px 0 0' }} />

      <div className="px-5 py-4">
        <div className="flex justify-between items-start">
          <div className="flex-1 min-w-0">
            <p
              className="text-xs font-medium tracking-widest uppercase mb-3"
              style={{ color: 'var(--whisper)' }}
            >
              {label}
            </p>
            <div className="flex items-baseline gap-2">
              <p
                className="text-3xl font-semibold tabular-nums leading-none"
                style={{ color: c.text, fontFamily: 'Fraunces, serif' }}
              >
                {value}
              </p>
              {trend && (
                <span
                  className="text-xs font-semibold px-1.5 py-0.5 rounded-full"
                  style={{
                    color: trend.isPositive ? 'var(--sage)' : 'var(--terra)',
                    background: trend.isPositive ? 'rgba(107,138,113,0.12)' : 'rgba(193,123,91,0.12)',
                  }}
                >
                  {trend.isPositive ? '↑' : '↓'} {Math.abs(trend.value)}%
                </span>
              )}
            </div>
          </div>

          {icon && (
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ml-3"
              style={{ background: c.accentBg, color: c.accent }}
            >
              {icon}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/* ── Button ───────────────────────────────────────────────────────────────── */
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  children: React.ReactNode;
}

const buttonVariants = {
  primary: {
    background: 'linear-gradient(135deg, var(--gold) 0%, var(--gold-light) 100%)',
    color: '#fff',
    border: '1px solid rgba(155,122,58,0.5)',
    boxShadow: '0 2px 12px rgba(155,122,58,0.28), inset 0 1px 0 rgba(255,255,255,0.18)',
    hoverShadow: '0 6px 20px rgba(155,122,58,0.38)',
    disabledBg: 'rgba(155,122,58,0.40)',
  },
  secondary: {
    background: 'var(--glass-bg)',
    color: 'var(--ink)',
    border: '1px solid var(--glass-border)',
    boxShadow: 'var(--glass-shadow)',
    hoverShadow: 'var(--glass-shadow-hover)',
    disabledBg: 'rgba(232,220,200,0.50)',
  },
  danger: {
    background: 'linear-gradient(135deg, var(--terra) 0%, #D4987A 100%)',
    color: '#fff',
    border: '1px solid rgba(193,123,91,0.5)',
    boxShadow: '0 2px 12px rgba(193,123,91,0.25)',
    hoverShadow: '0 6px 20px rgba(193,123,91,0.35)',
    disabledBg: 'rgba(193,123,91,0.40)',
  },
  ghost: {
    background: 'transparent',
    color: 'var(--muted)',
    border: '1px solid transparent',
    boxShadow: 'none',
    hoverShadow: 'none',
    disabledBg: 'transparent',
  },
};

const buttonSizes = {
  sm: { padding: '0.375rem 0.875rem', fontSize: '0.8125rem', borderRadius: '0.625rem', gap: '0.375rem' },
  md: { padding: '0.5rem 1.125rem', fontSize: '0.875rem', borderRadius: '0.75rem', gap: '0.5rem' },
  lg: { padding: '0.75rem 1.5rem', fontSize: '0.9375rem', borderRadius: '0.875rem', gap: '0.625rem' },
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  disabled,
  children,
  style,
  ...props
}) => {
  const v = buttonVariants[variant];
  const s = buttonSizes[size];
  const isDisabled = disabled || isLoading;

  const [hovered, setHovered] = React.useState(false);

  return (
    <button
      disabled={isDisabled}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="btn-press inline-flex items-center justify-center font-medium tracking-wide select-none disabled:cursor-not-allowed"
      style={{
        background: isDisabled ? v.disabledBg : v.background,
        color: v.color,
        border: v.border,
        boxShadow: hovered && !isDisabled ? v.hoverShadow : v.boxShadow,
        padding: s.padding,
        fontSize: s.fontSize,
        borderRadius: s.borderRadius,
        gap: s.gap,
        opacity: isDisabled ? 0.65 : 1,
        transition: 'box-shadow 0.2s ease, transform 0.12s ease, opacity 0.15s ease',
        ...style,
      }}
      {...props}
    >
      {isLoading && (
        <svg
          className="animate-spin"
          style={{ width: '14px', height: '14px', flexShrink: 0 }}
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {children}
    </button>
  );
};

/* ── Badge ────────────────────────────────────────────────────────────────── */
interface BadgeProps {
  children: React.ReactNode;
  variant?: 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'gray';
  size?: 'sm' | 'md';
}

const badgeStyles = {
  primary: { background: 'rgba(155,122,58,0.12)', color: 'var(--gold)', border: '1px solid rgba(155,122,58,0.22)' },
  success: { background: 'rgba(107,138,113,0.12)', color: 'var(--sage)', border: '1px solid rgba(107,138,113,0.22)' },
  warning: { background: 'rgba(176,128,48,0.12)', color: '#9B7030', border: '1px solid rgba(176,128,48,0.22)' },
  danger: { background: 'rgba(193,123,91,0.12)', color: 'var(--terra)', border: '1px solid rgba(193,123,91,0.22)' },
  info: { background: 'rgba(106,130,168,0.12)', color: '#5A72A0', border: '1px solid rgba(106,130,168,0.22)' },
  gray: { background: 'rgba(122,101,69,0.10)', color: 'var(--muted)', border: '1px solid rgba(122,101,69,0.18)' },
};

export const Badge: React.FC<BadgeProps> = ({ children, variant = 'primary', size = 'md' }) => {
  const s = badgeStyles[variant];
  return (
    <span
      className="inline-flex items-center font-semibold rounded-full"
      style={{
        ...s,
        padding: size === 'sm' ? '0.15rem 0.55rem' : '0.25rem 0.75rem',
        fontSize: size === 'sm' ? '0.7rem' : '0.75rem',
        letterSpacing: '0.03em',
      }}
    >
      {children}
    </span>
  );
};

/* ── Alert ────────────────────────────────────────────────────────────────── */
interface AlertProps {
  type: 'info' | 'warning' | 'error' | 'success';
  message: string;
  onClose?: () => void;
}

const alertStyles = {
  info: {
    bg: 'rgba(59, 130, 246, 0.1)',
    border: 'rgba(59, 130, 246, 0.3)',
    text: 'rgb(37, 99, 235)',
    icon: 'ⓘ',
  },
  warning: {
    bg: 'rgba(245, 158, 11, 0.1)',
    border: 'rgba(245, 158, 11, 0.3)',
    text: 'rgb(217, 119, 6)',
    icon: '⚠',
  },
  error: {
    bg: 'rgba(239, 68, 68, 0.1)',
    border: 'rgba(239, 68, 68, 0.3)',
    text: 'rgb(220, 38, 38)',
    icon: '✕',
  },
  success: {
    bg: 'rgba(34, 197, 94, 0.1)',
    border: 'rgba(34, 197, 94, 0.3)',
    text: 'rgb(22, 163, 74)',
    icon: '✓',
  },
};

export const Alert: React.FC<AlertProps> = ({ type, message, onClose }) => {
  const style = alertStyles[type];
  return (
    <div
      className="rounded-lg p-4 mb-4 flex items-start gap-3"
      style={{ backgroundColor: style.bg, border: `1px solid ${style.border}` }}
    >
      <span style={{ color: style.text, fontSize: '1.2rem', flexShrink: 0 }}>
        {style.icon}
      </span>
      <p style={{ color: style.text, flex: 1 }}>{message}</p>
      {onClose && (
        <button
          onClick={onClose}
          className="text-sm font-semibold flex-shrink-0"
          style={{ color: style.text, cursor: 'pointer' }}
        >
          ✕
        </button>
      )}
    </div>
  );
};

// SystemAlert is an alias for Alert
export const SystemAlert = Alert;
