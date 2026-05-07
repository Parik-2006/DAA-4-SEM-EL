// src/components/Layout.tsx

import React, {
  useState,
  useEffect,
  useRef,
} from 'react';

import {
  Link,
  useLocation,
  useNavigate,
} from 'react-router-dom';

import {
  Home,
  Clock,
  Users,
  LogOut,
  Menu,
  X,
  AlertCircle,
  CheckCircle,
  Upload,
  BookOpen,
  User,
  ChevronDown,
  BarChart2,
  Calendar,
} from 'lucide-react';

import {
  onAuthChange,
  signOut,
  getSessionToken,
} from '@/services/firebase/auth.service';

import {
  getStoredRole,
  isAdmin,
  isTeacher,
  isStudent,
} from '@/utils/roles';

import { useBackendHealthMonitor } from '../hooks/useBackendHealth';

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

type UserRole =
  | 'admin'
  | 'teacher'
  | 'student'
  | null;

interface LayoutProps {
  children: React.ReactNode;
  systemRunning?: boolean;
  lastSyncTime?: Date | null;
}

interface NavLink {
  label: string;
  path: string;
  icon: React.ReactNode;
  group?: string;
}

// ─────────────────────────────────────────────────────────────
// ─────────────────────────────────────────────────────────────
// Navigation
// ─────────────────────────────────────────────────────────────

const ADMIN_NAV: NavLink[] = [
  {
    label: 'Dashboard',
    path: '/dashboard',
    icon: <Home size={17} />,
  },
  {
    label: 'History',
    path: '/history',
    icon: <Clock size={17} />,
  },
  {
    label: 'Batch Attendance',
    path: '/batch-import',
    icon: <Upload size={17} />,
    group: 'Management',
  },
  {
    label: 'Analytics',
    path: '/analytics',
    icon: <BarChart2 size={17} />,
    group: 'Management',
  },
  {
    label: 'Student Management',
    path: '/student-management',
    icon: <Users size={17} />,
    group: 'Management',
  },
  {
    label: 'Course Management',
    path: '/course-management',
    icon: <BookOpen size={17} />,
    group: 'Management',
  },
  {
    label: 'Timetable',
    path: '/timetable',
    icon: <Calendar size={17} />,
    group: 'Management',
  },
  {
    label: 'Class Views',
    path: '/class-views',
    icon: <Calendar size={17} />,
    group: 'Management',
  },
];

const TEACHER_NAV: NavLink[] = [
  {
    label: 'Dashboard',
    path: '/dashboard',
    icon: <Home size={17} />,
  },
  {
    label: 'Mark Attendance',
    path: '/attendance',
    icon: <CheckCircle size={17} />,
  },
  {
    label: 'History',
    path: '/history',
    icon: <Clock size={17} />,
  },
];

const STUDENT_NAV: NavLink[] = [
  {
    label: 'Live Attendance',
    path: '/attendance',
    icon: <CheckCircle size={17} />,
  },
  {
    label: 'My History',
    path: '/history',
    icon: <Clock size={17} />,
  },
  {
    label: 'Status',
    path: '/status',
    icon: <AlertCircle size={17} />,
  },
];

function getNavLinks(role: UserRole): NavLink[] {
  switch (role) {
    case 'admin':
      return ADMIN_NAV;

    case 'teacher':
      return TEACHER_NAV;

    case 'student':
      return STUDENT_NAV;

    default:
      return [];
  }
}

// ─────────────────────────────────────────────────────────────
// Role Badge
// ─────────────────────────────────────────────────────────────

const ROLE_BADGE: Record<
  NonNullable<UserRole>,
  {
    label: string;
    bg: string;
    color: string;
  }
> = {
  admin: {
    label: 'Admin',
    bg: 'rgba(99,102,241,0.12)',
    color: '#6366F1',
  },

  teacher: {
    label: 'Teacher',
    bg: 'rgba(20,184,166,0.12)',
    color: '#14B8A6',
  },

  student: {
    label: 'Student',
    bg: 'rgba(245,158,11,0.12)',
    color: '#F59E0B',
  },
};

// ─────────────────────────────────────────────────────────────
// Layout
// ─────────────────────────────────────────────────────────────

export const Layout: React.FC<
  LayoutProps
> = ({
  children,
  systemRunning,
  lastSyncTime,
}) => {
  const {
    isHealthy,
    lastCheck,
  } = useBackendHealthMonitor(5000);

  const isSystemRunning =
    systemRunning ?? isHealthy;

  const effectiveLastSync =
    lastSyncTime ?? lastCheck;

  const [sidebarOpen, setSidebarOpen] =
    useState(true);

  const [dropdownOpen, setDropdownOpen] =
    useState(false);

  const [role, setRole] =
    useState<UserRole>(getStoredRole);

  const [currentUser, setCurrentUser] =
    useState<{
      displayName: string | null;
      email: string | null;
      photoURL: string | null;
    } | null>(null);

  const dropdownRef =
    useRef<HTMLDivElement>(null);

  const location = useLocation();

  const navigate = useNavigate();

  // ─────────────────────────────────────────────────────────
  // Role Sync
  // ─────────────────────────────────────────────────────────

  useEffect(() => {
    const syncRole = () => {
      setRole(getStoredRole());
    };

    window.addEventListener(
      'storage',
      syncRole
    );

    syncRole();

    return () => {
      window.removeEventListener(
        'storage',
        syncRole
      );
    };
  }, []);

  // ─────────────────────────────────────────────────────────
  // Auth Sync
  // ─────────────────────────────────────────────────────────

  useEffect(() => {
    const unsub = onAuthChange((user) => {
      if (user) {
        setCurrentUser({
          displayName: user.displayName,
          email: user.email,
          photoURL: user.photoURL,
        });
      } else {
        const email =
          sessionStorage.getItem('user_email');

        setCurrentUser({
          displayName:
            email?.split('@')[0] ?? 'User',
          email,
          photoURL: null,
        });
      }
    });

    return () => unsub();
  }, []);

  // ─────────────────────────────────────────────────────────
  // Close Dropdown Outside Click
  // ─────────────────────────────────────────────────────────

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(
          e.target as Node
        )
      ) {
        setDropdownOpen(false);
      }
    };

    document.addEventListener(
      'mousedown',
      handler
    );

    return () => {
      document.removeEventListener(
        'mousedown',
        handler
      );
    };
  }, []);

  // ─────────────────────────────────────────────────────────
  // Logout
  // ─────────────────────────────────────────────────────────

  const handleLogout = async () => {
    try {
      await signOut();
    } catch (err) {
      console.error(err);
    } finally {
      [
        'auth_token',
        'user_role',
        'user_email',
        'user_id',
      ].forEach((key) =>
        localStorage.removeItem(key)
      );

      sessionStorage.clear();

      navigate('/login', {
        replace: true,
      });
    }
  };

  // ─────────────────────────────────────────────────────────
  // Helpers
  // ─────────────────────────────────────────────────────────

  const getInitials = (
    name: string | null,
    email: string | null
  ) => {
    if (name) {
      return name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);
    }

    if (email) {
      return email[0].toUpperCase();
    }

    return '?';
  };

  const navLinks = getNavLinks(role);

  const visibleNavLinks = navLinks.filter((link) => {
    if (isAdmin(role)) {
      return true;
    }

    if (isTeacher(role)) {
      return link.path !== '/profile' && link.path !== '/qr-attendance' && link.path !== '/face-registration';
    }

    if (isStudent(role)) {
      return link.path !== '/profile' && link.path !== '/face-registration';
    }

    return false;
  });

  const currentPageLabel =
    navLinks.find(
      (n) => n.path === location.pathname
    )?.label ?? 'Dashboard';

  const badge =
    role && ROLE_BADGE[role];

  const displayName =
    currentUser?.displayName ||
    currentUser?.email?.split('@')[0] ||
    'User';

  // ─────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────

  return (
    <div
      className="flex h-screen overflow-hidden"
      style={{
        background: 'var(--cream-100)',
      }}
    >
      {/* SIDEBAR */}

      <aside
        className={`
          glass-sidebar
          flex-shrink-0
          flex
          flex-col
          transition-all
          duration-300
          overflow-hidden
          z-20
          ${sidebarOpen ? 'w-60' : 'w-[68px]'}
        `}
      >
        {/* HEADER */}

        <div className="flex items-center justify-between px-4 pt-6 pb-5">
          {sidebarOpen && (
            <div className="flex items-center gap-3">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center"
                style={{
                  background:
                    'linear-gradient(135deg,var(--gold) 0%,var(--gold-light) 100%)',
                }}
              >
                <span className="text-white font-bold text-sm">
                  A
                </span>
              </div>

              <div>
                <p className="text-sm font-semibold">
                  AttendMate
                </p>

                <p className="text-[10px] uppercase tracking-widest">
                  {badge?.label ?? 'Portal'}
                </p>
              </div>
            </div>
          )}

          <button
            onClick={() =>
              setSidebarOpen(!sidebarOpen)
            }
            className="p-1.5 rounded-lg"
          >
            {sidebarOpen ? (
              <X size={16} />
            ) : (
              <Menu size={16} />
            )}
          </button>
        </div>

        {/* ROLE BADGE */}

        {badge && sidebarOpen && (
          <div className="mx-3 mb-4">
            <span
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold"
              style={{
                background: badge.bg,
                color: badge.color,
              }}
            >
              <span
                className="w-2 h-2 rounded-full"
                style={{
                  background: badge.color,
                }}
              />

              {badge.label}
            </span>
          </div>
        )}

        {/* NAVIGATION */}

        <nav className="flex-1 px-3 space-y-1 overflow-y-auto">
          {visibleNavLinks.map((link) => {
            const isActive =
              location.pathname === link.path;

            return (
              <Link
                key={link.path}
                to={link.path}
                className={`
                  flex
                  items-center
                  rounded-xl
                  px-3
                  py-2.5
                  transition-all
                  ${sidebarOpen
                    ? 'gap-3'
                    : 'justify-center'}
                `}
                style={{
                  color: isActive
                    ? 'var(--gold)'
                    : 'var(--muted)',
                  fontWeight: isActive
                    ? 600
                    : 400,
                }}
              >
                {link.icon}

                {sidebarOpen && (
                  <span>{link.label}</span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* LOGOUT */}

        <div className="px-3 pb-5 pt-2">
          <button
            onClick={handleLogout}
            className={`
              w-full
              flex
              items-center
              rounded-xl
              px-3
              py-2.5
              ${sidebarOpen
                ? 'gap-3'
                : 'justify-center'}
            `}
          >
            <LogOut size={17} />

            {sidebarOpen && (
              <span>Sign Out</span>
            )}
          </button>
        </div>
      </aside>

      {/* MAIN */}

      <div className="flex-1 flex flex-col overflow-hidden">

        {/* TOPBAR */}

        <header className="glass-header px-7 py-3.5">
          <div className="flex items-center justify-between">

            <h2 className="text-xl font-semibold">
              {currentPageLabel}
            </h2>

            <div className="flex items-center gap-3">

              {/* STATUS */}

              <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{
                    background:
                      isSystemRunning
                        ? 'green'
                        : 'red',
                  }}
                />

                <span className="text-xs">
                  {isSystemRunning
                    ? 'Online'
                    : 'Offline'}
                </span>
              </div>

              {/* USER */}

              <div
                className="relative"
                ref={dropdownRef}
              >
                <button
                  onClick={() =>
                    setDropdownOpen(
                      !dropdownOpen
                    )
                  }
                  className="flex items-center gap-2"
                >
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-white"
                    style={{
                      background:
                        'linear-gradient(135deg,var(--gold),var(--gold-light))',
                    }}
                  >
                    {getInitials(
                      currentUser?.displayName ??
                        null,
                      currentUser?.email ?? null
                    )}
                  </div>

                  <span>
                    {displayName}
                  </span>

                  <ChevronDown size={14} />
                </button>

                {dropdownOpen && (
                  <div
                    className="absolute right-0 mt-2 w-56 rounded-2xl overflow-hidden z-50"
                    style={{
                      background:
                        'var(--glass-bg)',
                    }}
                  >
                    <div className="px-4 py-3 border-b">
                      <p className="font-semibold">
                        {displayName}
                      </p>

                      <p className="text-xs">
                        {currentUser?.email}
                      </p>
                    </div>

                    <Link
                      to="/profile"
                      className="flex items-center gap-3 px-4 py-3"
                    >
                      <User size={14} />
                      Profile
                    </Link>

                    <button
                      onClick={handleLogout}
                      className="w-full flex items-center gap-3 px-4 py-3 text-left"
                    >
                      <LogOut size={14} />
                      Sign Out
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* CONTENT */}

        <main className="flex-1 overflow-y-auto p-7">
          {children}
        </main>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// System Alert
// ─────────────────────────────────────────────────────────────

interface SystemAlertProps {
  systemRunning: boolean;
  error: string | null;
}

export const SystemAlert: React.FC<
  SystemAlertProps
> = ({
  systemRunning,
  error,
}) => {
  if (systemRunning && !error) {
    return null;
  }

  return (
    <div className="flex items-center gap-4 px-5 py-4 rounded-2xl">
      <AlertCircle size={18} />

      <div>
        <p className="font-semibold">
          {error
            ? 'System Error'
            : 'System Offline'}
        </p>

        <p className="text-sm">
          {error ??
            'Attendance system offline'}
        </p>
      </div>
    </div>
  );
};