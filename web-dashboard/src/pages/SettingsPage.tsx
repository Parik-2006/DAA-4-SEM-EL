import React, { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Save, RotateCcw } from 'lucide-react';
import { Layout } from '@/components';
import { Card, Button } from '@/components';

interface AppSettings {
  apiUrl: string;
  pollInterval: number;
  theme: 'light' | 'dark';
  enableNotifications: boolean;
  autoRefresh: boolean;
}

export const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<AppSettings>({
    apiUrl: localStorage.getItem('apiUrl') || 'http://localhost:8000',
    pollInterval:
      parseInt(localStorage.getItem('pollInterval') || '5000') / 1000,
    theme: (localStorage.getItem('theme') as 'light' | 'dark') || 'light',
    enableNotifications: localStorage.getItem('enableNotifications') !== 'false',
    autoRefresh: localStorage.getItem('autoRefresh') !== 'false',
  });

  const [saved, setSaved] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  const handleChange = (key: keyof AppSettings, value: any) => {
    setSettings((prev) => ({
      ...prev,
      [key]: value,
    }));
    setIsDirty(true);
  };

  const handleSave = () => {
    localStorage.setItem('apiUrl', settings.apiUrl);
    localStorage.setItem('pollInterval', String(settings.pollInterval * 1000));
    localStorage.setItem('theme', settings.theme);
    localStorage.setItem('enableNotifications', String(settings.enableNotifications));
    localStorage.setItem('autoRefresh', String(settings.autoRefresh));
    setIsDirty(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleReset = () => {
    setSettings({
      apiUrl: 'http://localhost:8000',
      pollInterval: 5,
      theme: 'light',
      enableNotifications: true,
      autoRefresh: true,
    });
    setIsDirty(true);
  };

  return (
    <Layout systemRunning={true} lastSyncTime={new Date()}>
      <div className="space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
          <p className="text-gray-600 mt-1">
            Configure your attendance dashboard
          </p>
        </div>

        {/* Success Alert */}
        {saved && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
            ✓ Settings saved successfully
          </div>
        )}

        {/* API Configuration */}
        <Card>
          <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
            <SettingsIcon size={24} className="text-indigo-600" />
            API Configuration
          </h2>

          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                API Base URL
              </label>
              <input
                type="text"
                value={settings.apiUrl}
                onChange={(e) => handleChange('apiUrl', e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent font-mono text-sm"
                placeholder="http://localhost:8000"
              />
              <p className="mt-2 text-xs text-gray-500">
                The base URL for the attendance API server. Update this if you
                deploy to a production server.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Polling Interval (seconds)
              </label>
              <input
                type="number"
                min="1"
                max="60"
                value={settings.pollInterval}
                onChange={(e) =>
                  handleChange('pollInterval', parseInt(e.target.value))
                }
                className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
              <p className="mt-2 text-xs text-gray-500">
                How often the dashboard refreshes data (1-60 seconds). Lower
                values = more frequent updates, higher CPU usage.
              </p>
            </div>
          </div>
        </Card>

        {/* Display Settings */}
        <Card>
          <h2 className="text-xl font-bold text-gray-900 mb-6">
            Display Settings
          </h2>

          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Theme
              </label>
              <select
                value={settings.theme}
                onChange={(e) =>
                  handleChange('theme', e.target.value as 'light' | 'dark')
                }
                className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              >
                <option value="light">Light</option>
                <option value="dark">Dark (Coming Soon)</option>
              </select>
            </div>
          </div>
        </Card>

        {/* Notification Settings */}
        <Card>
          <h2 className="text-xl font-bold text-gray-900 mb-6">
            Notifications
          </h2>

          <div className="space-y-4">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.enableNotifications}
                onChange={(e) =>
                  handleChange('enableNotifications', e.target.checked)
                }
                className="w-4 h-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span className="text-gray-700">
                Enable desktop notifications for attendance events
              </span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.autoRefresh}
                onChange={(e) =>
                  handleChange('autoRefresh', e.target.checked)
                }
                className="w-4 h-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span className="text-gray-700">
                Auto-refresh dashboard data
              </span>
            </label>
          </div>
        </Card>

        {/* About Section */}
        <Card className="bg-gradient-to-br from-indigo-50 to-purple-50 border-indigo-200">
          <div>
            <h3 className="font-bold text-gray-900 mb-2 text-lg">
              About This Dashboard
            </h3>
            <div className="space-y-2 text-sm text-gray-700">
              <p>
                <strong>Version:</strong> 1.0.0
              </p>
              <p>
                <strong>Platform:</strong> Web Dashboard for Smart Attendance
                System
              </p>
              <p>
                <strong>Built with:</strong> React 18.2, TypeScript 5, Tailwind
                CSS
              </p>
              <p className="mt-4">
                This dashboard displays real-time attendance data captured by
                camera-based face recognition. All data is processed and stored
                on your backend servers.
              </p>
            </div>
          </div>
        </Card>

        {/* Action Buttons */}
        <div className="flex gap-3 pt-4">
          <Button
            onClick={handleSave}
            variant="primary"
            disabled={!isDirty}
          >
            <Save size={20} />
            Save Changes
          </Button>
          <Button
            onClick={handleReset}
            variant="secondary"
          >
            <RotateCcw size={20} />
            Reset to Defaults
          </Button>
        </div>
      </div>
    </Layout>
  );
};
