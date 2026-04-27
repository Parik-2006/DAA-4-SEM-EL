import React, { useState, useEffect, useRef } from 'react';
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
  ChevronDown,
} from 'lucide-react';
import { Badge } from './UI';
import { onAuthChange, signOut } from '@/services/firebase/auth.service';

interface NavLink {
  label: string;
  path: string;
  icon: React.ReactNode;
  group?: string;
}

const navLinks: NavLink[] = [
  { label: 'Dashboard', path: '/dashboard', icon: <Home size={17} /> },
  { label: 'Mark Attendance', path: '/attendance', icon: <CheckCircle size={17} /> },
  { label: 'History', path: '/history', icon: <Clock size={17} /> },
  { label: 'Face Registration', path: '/face-registration', icon: <User size={17} />, group: 'Admin' },
  { label: 'QR Attendance', path: '/qr-attendance', icon: <QrCode size={17} />, group: 'Admin' },
  { label: 'Batch Import', path: '/batch-import', icon: <Upload size={17} />, group: 'Admin' },
  { label: 'Student Management', path: '/student-management', icon: <Users size={17} />, group: 'Admin' },
  { label: 'Course Management', path: '/course-management', icon: <BookOpen size={17} />, group: 'Admin' },
  { label: 'Settings', path: '/settings', icon: <Settings size={17} /> },
];

interface LayoutProps {
  children: React.ReactNode;
  systemRunning?: boolean;
  lastSyncTime?: Date | null;
}

export const Layout: React.FC<LayoutProps> = ({
  children,
  systemRunning,
  lastSyncTime,
}) => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [currentUser, setCurrentUser] = useState<{ displayName: string | null; email: string | null; photoURL: string | null } | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const unsubscribe = onAuthChange((user) => {
      if (user) {
        setCurrentUser({
          displayName: user.displayName,
          email: user.email,
          photoURL: user.photoURL,
        });
      } else {
        setCurrentUser(null);
      }
    });
    return () => unsubscribe();
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    try {
      await signOut();
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_id');
      navigate('/login');
    } catch (err) {
      console.error('Logout failed', err);
    }
  };

  const getInitials = (name: string | null, email: string | null) => {
    if (name) return name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);
    if (email) return email[0].toUpperCase();
    return '?';
  };

  const displayName = currentUser?.displayName || currentUser?.email?.split('@')[0] || 'User';

  const currentPageLabel = navLinks.find((link) => link.path === location.pathname)?.label || 'Dashboard';

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--cream-100)' }}>

      {/* ── Sidebar ──────────────────────────────────────────────────────────── */}
      <aside
        className={`
          glass-sidebar flex-shrink-0 flex flex-col
          transition-all duration-300 ease-in-out overflow-hidden z-20
          ${sidebarOpen ? 'w-60' : 'w-[68px]'}
        `}
      >
        {/* Logo Row */}
        <div className="flex items-center justify-between px-4 pt-6 pb-5">
          {sidebarOpen && (
            <div className="flex items-center gap-3 animate-fade-in">
              {/* Tactical emblem */}
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{
                  background: 'linear-gradient(135deg, var(--gold) 0%, var(--gold-light) 100%)',
                  boxShadow: '0 2px 8px rgba(155,122,58,0.35)'
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
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="rounded-lg p-1.5 btn-press flex-shrink-0 transition-colors"
            style={{ color: 'var(--muted)' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(155,122,58,0.10)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
          </button>
        </div>

        <div className="tac-divider mx-3 mb-4" />

        {/* Nav Links */}
        <nav className="flex-1 px-3 space-y-0.5 overflow-y-auto pb-4">
          {navLinks.map((link, index) => {
            const prevLink = index > 0 ? navLinks[index - 1] : null;
            const showGroupHeader = link.group && (!prevLink || prevLink.group !== link.group);
            const isActive = location.pathname === link.path;

            return (
              <div key={link.path}>
                {showGroupHeader && sidebarOpen && (
                  <div className="pt-5 pb-2 px-2">
                    <p
                      className="text-[10px] font-semibold tracking-[0.14em] uppercase"
                      style={{ color: 'var(--whisper)' }}
                    >
                      {link.group}
                    </p>
                  </div>
                )}
                {showGroupHeader && !sidebarOpen && (
                  <div className="pt-3 pb-1">
                    <div className="tac-divider mx-1" />
                  </div>
                )}

                <Link
                  to={link.path}
                  title={!sidebarOpen ? link.label : undefined}
                  className={`
                    nav-item flex items-center rounded-xl px-3 py-2.5
                    ${!sidebarOpen ? 'justify-center' : 'gap-3'}
                    ${isActive ? 'nav-active' : ''}
                  `}
                  style={{
                    color: isActive ? 'var(--gold)' : 'var(--muted)',
                    fontWeight: isActive ? '600' : '400',
                    fontSize: '0.8125rem',
                  }}
                  onMouseEnter={e => { if (!isActive) (e.currentTarget as HTMLElement).style.color = 'var(--ink)'; }}
                  onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLElement).style.color = 'var(--muted)'; }}
                >
                  <span className="flex-shrink-0" style={{ opacity: isActive ? 1 : 0.75 }}>{link.icon}</span>
                  {sidebarOpen && <span>{link.label}</span>}
                  {isActive && sidebarOpen && (
                    <span className="ml-auto w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: 'var(--gold)' }} />
                  )}
                </Link>
              </div>
            );
          })}
        </nav>

        {/* Logout */}
        <div className="px-3 pb-5 pt-2">
          <div className="tac-divider mb-3" />
          <button
            onClick={handleLogout}
            className={`
              nav-item w-full flex items-center rounded-xl px-3 py-2.5 btn-press
              ${!sidebarOpen ? 'justify-center' : 'gap-3'}
            `}
            style={{ color: 'var(--whisper)', fontSize: '0.8125rem' }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.color = 'var(--terra)';
              (e.currentTarget as HTMLElement).style.background = 'rgba(193,123,91,0.08)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.color = 'var(--whisper)';
              (e.currentTarget as HTMLElement).style.background = 'transparent';
            }}
            title={!sidebarOpen ? 'Sign Out' : undefined}
          >
            <LogOut size={17} className="flex-shrink-0" />
            {sidebarOpen && <span className="font-medium">Sign Out</span>}
          </button>
        </div>
      </aside>

      {/* ── Main Column ─────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">

        {/* Header */}
        <header className="glass-header flex-shrink-0 px-7 py-3.5 z-10">
          <div className="flex items-center justify-between">

            {/* Page title */}
            <div className="flex items-center gap-2">
              <h2
                className="text-xl font-semibold tracking-tight leading-none"
                style={{ fontFamily: 'Fraunces, serif', color: 'var(--ink)' }}
              >
                {currentPageLabel}
              </h2>
            </div>

            <div className="flex items-center gap-3">

              {/* System status */}
              <div
                className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full"
                style={{
                  background: systemRunning ? 'rgba(107,138,113,0.10)' : 'rgba(193,123,91,0.10)',
                  border: `1px solid ${systemRunning ? 'rgba(107,138,113,0.25)' : 'rgba(193,123,91,0.25)'}`,
                }}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${systemRunning ? 'pulse-gold' : ''}`}
                  style={{ background: systemRunning ? 'var(--sage)' : 'var(--terra)' }}
                />
                <span className="text-xs font-medium" style={{ color: systemRunning ? 'var(--sage)' : 'var(--terra)' }}>
                  {systemRunning ? 'Online' : 'Offline'}
                </span>
              </div>

              {/* Last sync */}
              {lastSyncTime && (
                <div
                  className="hidden lg:flex items-center gap-1.5 px-2.5 py-1.5 rounded-full"
                  style={{ background: 'rgba(155,122,58,0.08)', border: '1px solid rgba(155,122,58,0.15)' }}
                >
                  <Clock size={11} style={{ color: 'var(--gold)' }} />
                  <span className="text-[11px] font-mono" style={{ color: 'var(--muted)' }}>
                    {lastSyncTime.toLocaleTimeString()}
                  </span>
                </div>
              )}

              {/* User dropdown */}
              <div className="relative" ref={dropdownRef}>
                <button
                  onClick={() => setDropdownOpen(!dropdownOpen)}
                  className="flex items-center gap-2.5 pl-1.5 pr-3 py-1.5 rounded-full btn-press"
                  style={{
                    background: 'var(--glass-bg)',
                    border: '1px solid var(--glass-border)',
                    boxShadow: '0 2px 8px rgba(80,50,20,0.06)',
                  }}
                >
                  {currentUser?.photoURL ? (
                    <img src={currentUser.photoURL} alt={displayName} className="w-7 h-7 rounded-full object-cover" />
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
                    style={{
                      color: 'var(--muted)',
                      transform: dropdownOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                    }}
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

                    {[
                      { to: '/profile', icon: <User size={14} />, label: 'View Profile' },
                      { to: '/settings', icon: <Settings size={14} />, label: 'Settings' },
                    ].map(({ to, icon, label }) => (
                      <Link
                        key={to}
                        to={to}
                        onClick={() => setDropdownOpen(false)}
                        className="flex items-center gap-3 px-4 py-2.5 text-sm transition-colors"
                        style={{ color: 'var(--muted)' }}
                        onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(155,122,58,0.07)'; (e.currentTarget as HTMLElement).style.color = 'var(--ink)'; }}
                        onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; (e.currentTarget as HTMLElement).style.color = 'var(--muted)'; }}
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
                        onMouseEnter={e => (e.currentTarget.style.background = 'rgba(193,123,91,0.08)')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
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

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-7 md:p-8">
          {children}
        </main>
      </div>
    </div>
  );
};

/* ── System Alert ─────────────────────────────────────────────────────────── */
interface SystemAlertProps {
  systemRunning: boolean;
  error: string | null;
}

export const SystemAlert: React.FC<SystemAlertProps> = ({ systemRunning, error }) => {
  if (systemRunning && !error) return null;
  return (
    <div
      className="flex items-center gap-4 px-5 py-4 rounded-2xl animate-fade-in-up"
      style={{
        background: error ? 'rgba(193,123,91,0.10)' : 'rgba(200,168,106,0.12)',
        border: `1px solid ${error ? 'rgba(193,123,91,0.28)' : 'rgba(200,168,106,0.28)'}`,
      }}
    >
      <div
        className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
        style={{ background: error ? 'rgba(193,123,91,0.15)' : 'rgba(200,168,106,0.18)' }}
      >
        <AlertCircle size={16} style={{ color: error ? 'var(--terra)' : 'var(--gold)' }} />
      </div>
      <div>
        <p className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>
          {error ? 'System Error' : 'System Offline'}
        </p>
        <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
          {error || 'The attendance system is currently offline. Some features may be unavailable.'}
        </p>
      </div>
    </div>
  );
};
