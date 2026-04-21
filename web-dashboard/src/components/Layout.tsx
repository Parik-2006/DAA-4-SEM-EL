import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
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
} from 'lucide-react';
import { Badge } from './UI';

interface NavLink {
  label: string;
  path: string;
  icon: React.ReactNode;
}

const navLinks: NavLink[] = [
  { label: 'Dashboard', path: '/dashboard', icon: <Home size={20} /> },
  { label: 'Mark Attendance', path: '/attendance', icon: <CheckCircle size={20} /> },
  { label: 'History', path: '/history', icon: <Clock size={20} /> },
  { label: 'Students', path: '/students', icon: <Users size={20} /> },
  { label: 'Settings', path: '/settings', icon: <Settings size={20} /> },
];

interface LayoutProps {
  children: React.ReactNode;
  systemRunning: boolean;
  lastSyncTime: Date | null;
}

export const Layout: React.FC<LayoutProps> = ({
  children,
  systemRunning,
  lastSyncTime,
}) => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const location = useLocation();

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside
        className={`
          ${sidebarOpen ? 'w-64' : 'w-20'}
          bg-white border-r border-gray-100 transition-all duration-300
          flex flex-col overflow-hidden
        `}
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
        <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
          {navLinks.map((link) => (
            <Link
              key={link.path}
              to={link.path}
              className={`
                flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200
                ${
                  location.pathname === link.path
                    ? 'bg-indigo-50 text-indigo-600'
                    : 'text-gray-600 hover:bg-gray-50'
                }
              `}
            >
              {link.icon}
              {sidebarOpen && <span className="font-medium">{link.label}</span>}
            </Link>
          ))}
        </nav>

        {/* Logout */}
        <div className="p-4 border-t border-gray-100">
          <button
            className={`
              w-full flex items-center gap-3 px-4 py-3 rounded-lg
              text-gray-600 hover:bg-red-50 hover:text-red-600 transition-all duration-200
            `}
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
            <div className="flex-1">
              <h2 className="text-2xl font-bold text-gray-900">
                {navLinks.find((link) => link.path === location.pathname)
                  ?.label || 'Dashboard'}
              </h2>
            </div>
            <div className="flex items-center gap-4">
              {/* System Status */}
              <div className="flex items-center gap-2">
                <div
                  className={`
                    w-3 h-3 rounded-full animate-pulse
                    ${systemRunning ? 'bg-green-500' : 'bg-red-500'}
                  `}
                />
                <span className="text-sm text-gray-600">
                  {systemRunning ? 'System Online' : 'System Offline'}
                </span>
              </div>

              {/* Last Sync Time */}
              {lastSyncTime && (
                <div className="flex items-center gap-2 px-4 py-2 bg-gray-50 rounded-lg">
                  <Clock size={16} className="text-gray-400" />
                  <span className="text-sm text-gray-600">
                    Last sync: {lastSyncTime.toLocaleTimeString()}
                  </span>
                </div>
              )}

              {/* User Menu Placeholder */}
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-400 to-purple-600 flex items-center justify-center text-white font-bold cursor-pointer hover:shadow-lg transition-shadow">
                A
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

export const SystemAlert: React.FC<SystemAlertProps> = ({
  systemRunning,
  error,
}) => {
  if (systemRunning && !error) return null;

  return (
    <div
      className={`
        flex items-center gap-3 p-4 rounded-lg border
        ${
          error
            ? 'bg-red-50 border-red-200 text-red-700'
            : 'bg-yellow-50 border-yellow-200 text-yellow-700'
        }
      `}
    >
      <AlertCircle size={20} />
      <div>
        <p className="font-semibold">
          {error ? 'System Error' : 'System Offline'}
        </p>
        <p className="text-sm">
          {error
            ? error
            : 'The attendance system is currently offline. Some features may be unavailable.'}
        </p>
      </div>
    </div>
  );
};
