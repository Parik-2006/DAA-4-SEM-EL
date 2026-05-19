/**
 * Layout.tsx
 * ----------
 * Role-aware shell with sidebar navigation and user menu.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Home,
  Clock,
  Users,
  Settings,
  LogOut,
  Menu,
  X,
  AlertCircle,
  CheckCircle,
  QrCode,
  Upload,
  BookOpen,
  User,
  Camera,
  ChevronDown,
  BarChart2,
} from 'lucide-react';
import { onAuthChange, signOut, getStoredAssignedSections, getStoredClassId, getStoredEmail, getSessionToken } from '@/services/firebase/auth.service';
import { useBackendHealthMonitor } from '../hooks/useBackendHealth';
import useRealtimeChannel, { type EventEnvelope } from '../hooks/useRealtimeChannel';
import { getStoredRole, type UserRole } from '../utils/roles';

interface NavLinkItem {
  label: string;
  path: string;
  icon: React.ReactNode;
  group?: string;
}

const STAFF_NAV_LINKS: NavLinkItem[] = [
  { label: 'Dashboard', path: '/dashboard', icon: <Home size={17} /> },
  { label: 'Mark Attendance', path: '/attendance', icon: <CheckCircle size={17} /> },
  { label: 'History', path: '/history', icon: <Clock size={17} /> },
  { label: 'Analytics', path: '/analytics', icon: <BarChart2 size={17} /> },
  { label: 'Face Registration', path: '/face-registration', icon: <User size={17} />, group: 'Admin' },
  { label: 'QR Attendance', path: '/qr-attendance', icon: <QrCode size={17} />, group: 'Admin' },
  { label: 'Batch Import', path: '/batch-import', icon: <Upload size={17} />, group: 'Admin' },
  { label: 'Student Management', path: '/student-management', icon: <Users size={17} />, group: 'Admin' },
  { label: 'Course Management', path: '/course-management', icon: <BookOpen size={17} />, group: 'Admin' },
  { label: 'Settings', path: '/settings', icon: <Settings size={17} /> },
];

const STUDENT_NAV_LINKS: NavLinkItem[] = [
  { label: 'Dashboard', path: '/dashboard', icon: <Home size={17} /> },
  { label: 'History', path: '/history', icon: <Clock size={17} /> },
  { label: 'Analytics', path: '/analytics', icon: <BarChart2 size={17} /> },
  { label: 'Live Camera', path: '/face', icon: <Camera size={17} /> },
];

function getNavLinks(role: UserRole | null): NavLinkItem[] {
  return role === 'student' ? STUDENT_NAV_LINKS : STAFF_NAV_LINKS;
}

function getRoleBadge(role: UserRole | null): { label: string; color: string; background: string; border: string } {
  if (role === 'admin') {
    return { label: 'ADMIN', color: '#A16207', background: 'rgba(245, 158, 11, 0.12)', border: 'rgba(245, 158, 11, 0.26)' };
  }
  if (role === 'teacher') {
    return { label: 'TEACHER', color: '#0F766E', background: 'rgba(20, 184, 166, 0.12)', border: 'rgba(20, 184, 166, 0.26)' };
  }
  return { label: 'STUDENT', color: '#4338CA', background: 'rgba(99, 102, 241, 0.12)', border: 'rgba(99, 102, 241, 0.26)' };
}

const RealtimeAttendanceBridge: React.FC<{ sectionId: string; role: UserRole | null; clientId: string; token?: string | null }> = ({ sectionId, role, clientId, token }) => {
  const handleEvent = useCallback((env: EventEnvelope) => {
    if (!env.event || !['attendance_marked', 'bulk_attendance', 'attendance_updated'].includes(env.event)) return;
    const detail = { ...env, payload: env.payload ?? {} };
    try {
      window.dispatchEvent(new CustomEvent('attendance:marked', { detail }));
      window.dispatchEvent(new CustomEvent('attendance:updated', { detail }));
      window.localStorage.setItem('attendance_last_updated', new Date().toISOString());
    } catch (error) {
      console.warn('[Layout] Failed to dispatch attendance update:', error);
    }
  }, []);

  useRealtimeChannel({
    clientId,
    sectionId,
    role: role ?? 'student',
    token: token ?? undefined,
    onEvent: handleEvent,
  });

  return null;
};

interface LayoutProps {
  children: React.ReactNode;
  systemRunning?: boolean;
  lastSyncTime?: Date | null;
}

export const Layout: React.FC<LayoutProps> = ({ children, systemRunning, lastSyncTime }) => {
  const { isHealthy, lastCheck } = useBackendHealthMonitor(5000);
  const isSystemRunning = systemRunning ?? isHealthy;
  const effectiveLastSyncTime = lastSyncTime ?? lastCheck;
  const role = getStoredRole();
  const navLinks = useMemo(() => getNavLinks(role), [role]);
  const roleBadge = useMemo(() => getRoleBadge(role), [role]);

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [currentUser, setCurrentUser] = useState<{
    displayName: string | null;
    email: string | null;
    photoURL: string | null;
  } | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const dropdownRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    let unsubscribe = () => {};

    try {
      unsubscribe = onAuthChange((user) => {
        try {
          if (user) {
            setCurrentUser({
              displayName: user.displayName,
              email: user.email,
              photoURL: user.photoURL,
            });
          } else {
            setCurrentUser(null);
          }
        } catch (error) {
          console.error('[Layout] auth state update failed:', error);
        }
      });
    } catch (error) {
      console.error('[Layout] auth listener failed:', error);
    }

    return () => {
      try {
        unsubscribe();
      } catch (error) {
        console.error('[Layout] auth unsubscribe failed:', error);
      }
    };
  }, []);

  useEffect(() => {
    try {
      const storedEmail = localStorage.getItem('user_email');
      if (!currentUser && storedEmail) {
        setCurrentUser({
          displayName: storedEmail.split('@')[0],
          email: storedEmail,
          photoURL: null,
        });
      }
    } catch (error) {
      console.error('[Layout] stored user lookup failed:', error);
    }
  }, [currentUser]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    try {
      await signOut();
      ['auth_token', 'user_id', 'user_email', 'user_role'].forEach((key) => localStorage.removeItem(key));
      navigate('/login');
    } catch (error) {
      console.error('Logout failed', error);
    }
  };

  const displayName = currentUser?.displayName || currentUser?.email?.split('@')[0] || 'User';
  const currentPageLabel = navLinks.find((link) => link.path === location.pathname)?.label || 'Dashboard';

  const getInitials = (name: string | null, email: string | null) => {
    if (name) return name.split(' ').map((part) => part[0]).join('').toUpperCase().slice(0, 2);
    if (email) return email[0].toUpperCase();
    return '?';
  };

  const realtimeSectionIds = useMemo(() => {
    if (role === 'admin') return ['ADMIN_GLOBAL'];
    if (role === 'teacher') {
      const sections = getStoredAssignedSections();
      return sections.length > 0 ? sections : [getStoredClassId() ?? ''];
    }
    const classId = getStoredClassId();
    return classId ? [classId] : [];
  }, [role]);
  const realtimeClientId = useMemo(() => currentUser?.email ?? getStoredEmail() ?? sessionStorage.getItem('user_id') ?? '', [currentUser?.email]);
  const realtimeToken = useMemo(() => getSessionToken(), []);
  const shortcuts = role === 'student'
    ? [{ to: '/profile', icon: <User size={14} />, label: 'View Profile' }]
    : [
        { to: '/profile', icon: <User size={14} />, label: 'View Profile' },
        { to: '/analytics', icon: <BarChart2 size={14} />, label: 'Analytics' },
        { to: '/settings', icon: <Settings size={14} />, label: 'Settings' },
      ];

  return (
    <>
      {isSystemRunning && realtimeSectionIds.filter(Boolean).map((sectionId) => (
        <RealtimeAttendanceBridge
          key={sectionId}
          sectionId={sectionId}
          role={role}
          clientId={realtimeClientId}
          token={realtimeToken}
        />
      ))}
      <div className="flex h-screen overflow-hidden" style={{ background: 'var(--cream-100)' }}>
        <aside
          className={`glass-sidebar flex-shrink-0 flex flex-col transition-all duration-300 ease-in-out overflow-hidden z-20 ${sidebarOpen ? 'w-60' : 'w-[68px]'}`}
        >
          <div className="flex items-center justify-between px-4 pt-6 pb-5">
            {sidebarOpen && (
              <div className="flex items-center gap-3 animate-fade-in">
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{
                    background: 'linear-gradient(135deg, var(--gold) 0%, var(--gold-light) 100%)',
                    boxShadow: '0 2px 8px rgba(155,122,58,0.35)',
                  }}
                >
                  <span className="text-white font-bold text-sm" style={{ fontFamily: 'Fraunces, serif' }}>A</span>
                </div>
                <div>
                  <p className="text-sm font-semibold tracking-tight leading-none" style={{ color: 'var(--ink)', fontFamily: 'Fraunces, serif' }}>
                    AttendMate
                  </p>
                  <p className="text-[10px] mt-0.5 tracking-widest uppercase" style={{ color: 'var(--whisper)' }}>
                    Command
                  </p>
                </div>
              </div>
            )}

            <button
              onClick={() => setSidebarOpen((open) => !open)}
              className="rounded-lg p-1.5 btn-press flex-shrink-0 transition-colors"
              style={{ color: 'var(--muted)' }}
              onMouseEnter={(event) => (event.currentTarget.style.background = 'rgba(155,122,58,0.10)')}
              onMouseLeave={(event) => (event.currentTarget.style.background = 'transparent')}
            >
              {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
            </button>
          </div>

          <div className="tac-divider mx-3 mb-4" />

          <nav className="flex-1 px-3 space-y-0.5 overflow-y-auto pb-4">
            {navLinks.map((link, index) => {
              const previousLink = index > 0 ? navLinks[index - 1] : null;
              const showGroup = Boolean(link.group && (!previousLink || previousLink.group !== link.group));
              const isActive = location.pathname === link.path;

              return (
                <div key={link.path}>
                  {showGroup && sidebarOpen && (
                    <div className="pt-5 pb-2 px-2">
                      <p className="text-[10px] font-semibold tracking-[0.14em] uppercase" style={{ color: 'var(--whisper)' }}>
                        {link.group}
                      </p>
                    </div>
                  )}
                  {showGroup && !sidebarOpen && (
                    <div className="pt-3 pb-1">
                      <div className="tac-divider mx-1" />
                    </div>
                  )}

                  <Link
                    to={link.path}
                    title={!sidebarOpen ? link.label : undefined}
                    className={[
                      'nav-item flex items-center rounded-xl px-3 py-2.5',
                      !sidebarOpen ? 'justify-center' : 'gap-3',
                      isActive ? 'nav-active' : '',
                    ].join(' ')}
                    style={{
                      color: isActive ? 'var(--gold)' : 'var(--muted)',
                      fontWeight: isActive ? '600' : '400',
                      fontSize: '0.8125rem',
                    }}
                    onMouseEnter={(event) => {
                      if (!isActive) (event.currentTarget as HTMLElement).style.color = 'var(--ink)';
                    }}
                    onMouseLeave={(event) => {
                      if (!isActive) (event.currentTarget as HTMLElement).style.color = 'var(--muted)';
                    }}
                  >
                    <span className="flex-shrink-0" style={{ opacity: isActive ? 1 : 0.75 }}>
                      {link.icon}
                    </span>
                    {sidebarOpen && <span>{link.label}</span>}
                    {isActive && sidebarOpen && (
                      <span className="ml-auto w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: 'var(--gold)' }} />
                    )}
                  </Link>
                </div>
              );
            })}
          </nav>

          <div className="px-3 pb-5 pt-2">
            <div className="tac-divider mb-3" />
            <button
              onClick={handleLogout}
              className={[
                'nav-item w-full flex items-center rounded-xl px-3 py-2.5 btn-press',
                !sidebarOpen ? 'justify-center' : 'gap-3',
              ].join(' ')}
              style={{ color: 'var(--whisper)', fontSize: '0.8125rem' }}
              onMouseEnter={(event) => {
                event.currentTarget.style.color = 'var(--terra)';
                event.currentTarget.style.background = 'rgba(193,123,91,0.08)';
              }}
              onMouseLeave={(event) => {
                event.currentTarget.style.color = 'var(--whisper)';
                event.currentTarget.style.background = 'transparent';
              }}
              title={!sidebarOpen ? 'Sign Out' : undefined}
            >
              <LogOut size={17} className="flex-shrink-0" />
              {sidebarOpen && <span className="font-medium">Sign Out</span>}
            </button>
          </div>
        </aside>

        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          <header className="glass-header flex-shrink-0 px-7 py-3.5 z-10">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold tracking-tight leading-none" style={{ fontFamily: 'Fraunces, serif', color: 'var(--ink)' }}>
                {currentPageLabel}
              </h2>

              <div className="flex items-center gap-3">
                <div
                  className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full"
                  style={{
                    background: roleBadge.background,
                    border: `1px solid ${roleBadge.border}`,
                  }}
                >
                  <span
                    className="inline-flex h-2 w-2 rounded-full"
                    style={{ background: roleBadge.color }}
                  />
                  <span className="text-[11px] font-semibold tracking-[0.16em]" style={{ color: roleBadge.color }}>
                    {roleBadge.label}
                  </span>
                  <span className="text-[11px] text-[color:var(--muted)] max-w-[140px] truncate">
                    {currentUser?.email ?? role}
                  </span>
                </div>

                <div
                  className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full"
                  style={{
                    background: isSystemRunning ? 'rgba(107,138,113,0.10)' : 'rgba(193,123,91,0.10)',
                    border: `1px solid ${isSystemRunning ? 'rgba(107,138,113,0.25)' : 'rgba(193,123,91,0.25)'}`,
                  }}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isSystemRunning ? 'pulse-gold' : ''}`}
                    style={{ background: isSystemRunning ? 'var(--sage)' : 'var(--terra)' }}
                  />
                  <span className="text-xs font-medium" style={{ color: isSystemRunning ? 'var(--sage)' : 'var(--terra)' }}>
                    {isSystemRunning ? 'Online' : 'Offline'}
                  </span>
                </div>

                {effectiveLastSyncTime && (
                  <div
                    className="hidden lg:flex items-center gap-1.5 px-2.5 py-1.5 rounded-full"
                    style={{ background: 'rgba(155,122,58,0.08)', border: '1px solid rgba(155,122,58,0.15)' }}
                  >
                    <Clock size={11} style={{ color: 'var(--gold)' }} />
                    <span className="text-[11px] font-mono" style={{ color: 'var(--muted)' }}>
                      {effectiveLastSyncTime.toLocaleTimeString()}
                    </span>
                  </div>
                )}

                <div className="relative" ref={dropdownRef}>
                  <button
                    onClick={() => setDropdownOpen((open) => !open)}
                    className="flex items-center gap-2.5 pl-1.5 pr-3 py-1.5 rounded-full btn-press"
                    style={{
                      background: 'var(--glass-bg)',
                      border: '1px solid var(--glass-border)',
                      boxShadow: '0 2px 8px rgba(80,50,20,0.06)',
                    }}
                  >
                    {currentUser?.photoURL ? (
                      <img src={currentUser.photoURL ?? undefined} alt={displayName} className="w-7 h-7 rounded-full object-cover" />
                    ) : (
                      <div
                        className="w-7 h-7 rounded-full flex items-center justify-center text-white text-[11px] font-bold flex-shrink-0"
                        style={{ background: 'linear-gradient(135deg, var(--gold) 0%, var(--gold-light) 100%)' }}
                      >
                        {getInitials(currentUser?.displayName ?? null, currentUser?.email ?? null)}
                      </div>
                    )}
                    <span className="text-sm font-medium max-w-[100px] truncate" style={{ color: 'var(--ink)' }}>
                      {displayName}
                    </span>
                    <ChevronDown
                      size={13}
                      className="transition-transform duration-200"
                      style={{ color: 'var(--muted)', transform: dropdownOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}
                    />
                  </button>

                  {dropdownOpen && (
                    <div
                      className="absolute right-0 top-full mt-2 w-52 rounded-2xl overflow-hidden animate-scale-in z-50"
                      style={{
                        background: 'var(--glass-bg-hover)',
                        backdropFilter: 'var(--blur-md)',
                        WebkitBackdropFilter: 'var(--blur-md)',
                        border: '1px solid var(--glass-border)',
                        boxShadow: 'var(--glass-shadow-lg)',
                      }}
                    >
                      <div className="px-4 py-3" style={{ borderBottom: '1px solid rgba(190,160,118,0.20)' }}>
                        <p className="text-sm font-semibold truncate" style={{ color: 'var(--ink)' }}>{displayName}</p>
                        <p className="text-xs truncate mt-0.5" style={{ color: 'var(--muted)' }}>{currentUser?.email}</p>
                      </div>

                      {shortcuts.map(({ to, icon, label }) => (
                        <Link
                          key={to}
                          to={to}
                          onClick={() => setDropdownOpen(false)}
                          className="flex items-center gap-3 px-4 py-2.5 text-sm transition-colors"
                          style={{ color: 'var(--muted)' }}
                          onMouseEnter={(event) => {
                            (event.currentTarget as HTMLElement).style.background = 'rgba(155,122,58,0.07)';
                            (event.currentTarget as HTMLElement).style.color = 'var(--ink)';
                          }}
                          onMouseLeave={(event) => {
                            (event.currentTarget as HTMLElement).style.background = 'transparent';
                            (event.currentTarget as HTMLElement).style.color = 'var(--muted)';
                          }}
                        >
                          <span style={{ color: 'var(--whisper)' }}>{icon}</span>
                          {label}
                        </Link>
                      ))}

                      <div className="mt-1 pt-1" style={{ borderTop: '1px solid rgba(190,160,118,0.20)' }}>
                        <button
                          onClick={handleLogout}
                          className="w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors"
                          style={{ color: 'var(--terra)' }}
                          onMouseEnter={(event) => (event.currentTarget.style.background = 'rgba(193,123,91,0.08)')}
                          onMouseLeave={(event) => (event.currentTarget.style.background = 'transparent')}
                        >
                          <LogOut size={14} />
                          Sign Out
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </header>

          <main className="flex-1 overflow-y-auto p-7 md:p-8">
            {children}
          </main>
        </div>
      </div>
    </>
  );
};

/* ── SystemAlert ───────────────────────────────────────────────────────────── */

interface SystemAlertProps {
  type:     'info' | 'warning' | 'error' | 'success';
  message:  string;
  onClose?: () => void;
}

export const SystemAlert: React.FC<SystemAlertProps> = ({ type, message, onClose }) => {
  const styles = {
    warning: { bg: 'rgba(200,168,106,0.12)', border: 'rgba(200,168,106,0.28)', color: 'var(--gold)'  },
    error:   { bg: 'rgba(193,123,91,0.10)',  border: 'rgba(193,123,91,0.28)',  color: 'var(--terra)' },
    info:    { bg: 'rgba(59,130,246,0.08)',  border: 'rgba(59,130,246,0.25)',  color: '#3B82F6'      },
    success: { bg: 'rgba(107,138,113,0.10)', border: 'rgba(107,138,113,0.28)', color: 'var(--sage)' },
  };
  const s = styles[type];

  return (
    <div
      className="flex items-center gap-4 px-5 py-4 rounded-2xl animate-fade-in-up mb-4"
      style={{ background: s.bg, border: `1px solid ${s.border}` }}
    >
      <AlertCircle size={16} style={{ color: s.color, flexShrink: 0 }} />
      <p className="text-sm flex-1" style={{ color: 'var(--ink)' }}>{message}</p>
      {onClose && (
        <button onClick={onClose} style={{ color: s.color, background: 'none', border: 'none', cursor: 'pointer' }}>
          <X size={14} />
        </button>
      )}
    </div>
  );
};