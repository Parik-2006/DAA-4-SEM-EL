import React, { useEffect } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom';
import { useDashboardStore } from '@/store';
import {
  DashboardPage,
  HistoryPage,
  StudentsPage,
  SettingsPage,
} from '@/pages';

function App() {
  const { setCourses } = useDashboardStore();

  useEffect(() => {
    // Initialize app
    // Load initial settings from localStorage
    const apiUrl =
      localStorage.getItem('apiUrl') || 'http://localhost:8000';
    const pollInterval =
      parseInt(localStorage.getItem('pollInterval') || '5000') / 1000;

    console.log('App initialized with settings:', {
      apiUrl,
      pollInterval,
    });
  }, []);

  return (
    <Router>
      <Routes>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/students" element={<StudentsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
