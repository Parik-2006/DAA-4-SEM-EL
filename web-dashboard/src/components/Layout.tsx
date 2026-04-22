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
  { label: 'Dashboard', path: '/dashboard', icon: <Home size={20} /> },
  { label: 'Mark Attendance', path: '/attendance', icon: <CheckCircle size={20} /> },
  { label: 'History', path: '/history', icon: <Clock size={20} /> },
  { label: 'Face Registration', path: '/face-registration', icon: <User size={20} />, group: 'Admin' },
  { label: 'QR Attendance', path: '/qr-attendance', icon: <QrCode size={20} />, group: 'Admin' },
  { label: 'Batch Import', path: '/batch-import', icon: <Upload size={20} />, group: 'Admin' },
  { label: 'Student Management', path: '/student-management', icon: <Users size={20} />, group: 'Admin' },
  { label: 'Course Management', path: '/course-management', icon: <BookOpen size={20} />, group: 'Admin' },
  { label: 'Settings', path: '/settings', icon: <Settings size={20} /> },
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

  // Close dropdown when clicking outside
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
    if (name) {
      return name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);
    }
    if (email) return email[0].toUpperCase();
    return '?';
  };

  const displayName = currentUser?.displayName || currentUser?.email?.split('@')[0] || 'User';

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside
        className={`${sidebarOpen ? 'w-64' : 'w-20'} bg-white border-r border-gray-100 transition-all duration-300 flex flex-col overflow-hidden`}
      >
        {/* Logo */}
        <div className="p-6 border-b border-gray-100 flex items-center justify-between">
          {sidebarOpen && (
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">A</span>
              </div>
              <div>
                <h1 className="text-lg font-bold text-gray-900">Attendance</h1>
                <p className="text-xs text-gray-500">Dashboard</p>
              </div>
            </div>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
          {navLinks.map((link, index) => {
            const prevLink = index > 0 ? navLinks[index - 1] : null;
            const showGroupHeader = link.group && (!prevLink || prevLink.group !== link.group);
            return (
              <div key={link.path}>
                {showGroupHeader && sidebarOpen && (
                  <div className="px-4 py-2 mt-4 mb-1">
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                      {link.group}
                    </p>
                  </div>
                )}
                <Link
                  to={link.path}
                  className={`flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all duration-200 ${location.pathname === link.path
                      ? 'bg-indigo-50 text-indigo-600 font-medium'
                      : 'text-gray-600 hover:bg-gray-50'
                    }`}
                >
                  {link.icon}
                  {sidebarOpen && <span>{link.label}</span>}
                </Link>
              </div>
            );
          })}
        </nav>

        {/* Logout */}
        <div className="p-4 border-t border-gray-100">
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-gray-600 hover:bg-red-50 hover:text-red-600 transition-all duration-200"
          >
            <LogOut size={20} />
            {sidebarOpen && <span className="font-medium">Logout</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <header className="bg-white border-b border-gray-100 px-8 py-4">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-gray-900">
              {navLinks.find((link) => link.path === location.pathname)?.label || 'Dashboard'}
            </h2>

            <div className="flex items-center gap-4">
              {/* System Status */}
              <div className="flex items-center gap-2">
                <div className={`w-2.5 h-2.5 rounded-full ${systemRunning ? 'bg-green-500 animate-pulse' : 'bg-red-400'}`} />
                <span className="text-sm text-gray-500">
                  {systemRunning ? 'Online' : 'Offline'}
                </span>
              </div>

              {/* Last Sync Time */}
              {lastSyncTime && (
                <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-gray-50 rounded-lg">
                  <Clock size={14} className="text-gray-400" />
                  <span className="text-xs text-gray-500">
                    {lastSyncTime.toLocaleTimeString()}
                  </span>
                </div>
              )}

              {/* User Profile Dropdown */}
              <div className="relative" ref={dropdownRef}>
                <button
                  onClick={() => setDropdownOpen(!dropdownOpen)}
                  className="flex items-center gap-2 pl-1 pr-3 py-1 rounded-full bg-gray-50 hover:bg-gray-100 border border-gray-200 transition-colors"
                >
                  {currentUser?.photoURL ? (
                    <img
                      src={currentUser.photoURL}
                      alt={displayName}
                      className="w-8 h-8 rounded-full object-cover"
                    />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold">
                      {getInitials(currentUser?.displayName ?? null, currentUser?.email ?? null)}
                    </div>
                  )}
                  <span className="text-sm font-medium text-gray-700 max-w-[120px] truncate">
                    {displayName}
                  </span>
                  <ChevronDown size={14} className="text-gray-400" />
                </button>

                {dropdownOpen && (
                  <div className="absolute right-0 top-full mt-2 w-56 bg-white rounded-xl shadow-lg border border-gray-100 py-2 z-50">
                    {/* User info at top */}
                    <div className="px-4 py-3 border-b border-gray-100">
                      <p className="text-sm font-semibold text-gray-900 truncate">{displayName}</p>
                      <p className="text-xs text-gray-500 truncate mt-0.5">{currentUser?.email}</p>
                    </div>

                    <Link
                      to="/profile"
                      onClick={() => setDropdownOpen(false)}
                      className="flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                    >
                      <User size={16} className="text-gray-400" />
                      View Profile
                    </Link>
                    <Link
                      to="/settings"
                      onClick={() => setDropdownOpen(false)}
                      className="flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                    >
                      <Settings size={16} className="text-gray-400" />
                      Settings
                    </Link>

                    <div className="border-t border-gray-100 mt-1 pt-1">
                      <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
                      >
                        <LogOut size={16} />
                        Sign Out
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-8">{children}</main>
      </div>
    </div>
  );
};

interface SystemAlertProps {
  systemRunning: boolean;
  error: string | null;
}

export const SystemAlert: React.FC<SystemAlertProps> = ({ systemRunning, error }) => {
  if (systemRunning && !error) return null;
  return (
    <div
      className={`flex items-center gap-3 p-4 rounded-lg border ${error
          ? 'bg-red-50 border-red-200 text-red-700'
          : 'bg-yellow-50 border-yellow-200 text-yellow-700'
        }`}
    >
      <AlertCircle size={20} />
      <div>
        <p className="font-semibold">{error ? 'System Error' : 'System Offline'}</p>
        <p className="text-sm">
          {error || 'The attendance system is currently offline. Some features may be unavailable.'}
        </p>
      </div>
    </div>
  );
};
