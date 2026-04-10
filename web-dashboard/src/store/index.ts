import { create } from 'zustand';
import { AttendanceRecord, AttendanceStats, Course, Student } from '@/services/api';

export interface DashboardState {
  // System Status
  systemRunning: boolean;
  lastSyncTime: Date | null;
  isPolling: boolean;
  error: string | null;

  // Data
  liveRecords: AttendanceRecord[];
  stats: AttendanceStats | null;
  students: Student[];
  courses: Course[];
  selectedCourse: string | null;

  // UI
  showSuccess: boolean;
  successMessage: string;

  // Actions
  setSystemRunning: (running: boolean) => void;
  setLastSyncTime: (time: Date) => void;
  setIsPolling: (polling: boolean) => void;
  setError: (error: string | null) => void;
  setLiveRecords: (records: AttendanceRecord[]) => void;
  setStats: (stats: AttendanceStats | null) => void;
  setStudents: (students: Student[]) => void;
  setCourses: (courses: Course[]) => void;
  setSelectedCourse: (courseId: string | null) => void;
  showSuccessNotification: (message: string) => void;
  clearSuccessNotification: () => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  // Initial state
  systemRunning: false,
  lastSyncTime: null,
  isPolling: false,
  error: null,
  liveRecords: [],
  stats: null,
  students: [],
  courses: [],
  selectedCourse: null,
  showSuccess: false,
  successMessage: '',

  // Actions
  setSystemRunning: (running) => set({ systemRunning: running }),
  setLastSyncTime: (time) => set({ lastSyncTime: time }),
  setIsPolling: (polling) => set({ isPolling: polling }),
  setError: (error) => set({ error }),
  setLiveRecords: (records) => set({ liveRecords: records }),
  setStats: (stats) => set({ stats }),
  setStudents: (students) => set({ students }),
  setCourses: (courses) => set({ courses }),
  setSelectedCourse: (courseId) => set({ selectedCourse: courseId }),
  showSuccessNotification: (message) =>
    set({ showSuccess: true, successMessage: message }),
  clearSuccessNotification: () =>
    set({ showSuccess: false, successMessage: '' }),
}));
