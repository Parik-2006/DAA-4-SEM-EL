export interface AnalyticsMatrixSlot {
  slot_key: string;
  start_time: string;
  end_time: string;
  label: string;
}

export interface AnalyticsMatrixPeriodCell {
  period_id: string;
  course_code: string;
  course_name: string;
  faculty_id: string;
  faculty_name: string;
  room: string;
  is_lab_class: boolean;
}

export interface AnalyticsMatrixCell {
  slot_key: string;
  period: AnalyticsMatrixPeriodCell | null;
  status: 'no_class' | 'upcoming' | 'in_progress' | 'complete';
  total: number;
  marked: number;
  pending: number;
  present: number;
  late: number;
  absent: number;
  attendance_rate: number;
  window_locked: boolean;
  is_live: boolean;
}

export interface AnalyticsMatrixDay {
  day_index: number;
  day_name: string;
  date: string;
  cells: AnalyticsMatrixCell[];
  totals: {
    present: number;
    late: number;
    absent: number;
    marked: number;
    pending: number;
    total: number;
    attendance_rate: number;
  };
}

export interface AnalyticsMatrixSummary {
  total_students: number;
  total_periods: number;
  marked: number;
  pending: number;
  present: number;
  late: number;
  absent: number;
  attendance_rate: number;
}

export interface AttendanceMatrixResponse {
  class_id: string;
  class_name: string;
  section_label: string;
  semester: string;
  week_start: string;
  days: Array<{ day_index: number; day_name: string; date: string }>;
  period_slots: AnalyticsMatrixSlot[];
  rows: AnalyticsMatrixDay[];
  summary: AnalyticsMatrixSummary;
  generated_at: string;
}

export interface AttendanceRoleSummaryResponse {
  role: 'admin';
  student_count: number;
  class_count: number;
  today_breakdown: {
    present: number;
    late: number;
    absent: number;
    marked: number;
    attendance_rate: number;
  };
  active_period: Record<string, unknown> | null;
  at_risk_sections: Array<{
    class_id: string;
    class_name: string;
    attendance_rate: number;
    marked: number;
    total_students: number;
  }>;
  generated_at: string;
}
