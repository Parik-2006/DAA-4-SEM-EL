/**
 * timetable.ts
 * -----------
 * Single source of truth for CSE 4C Section C timetable.
 * RV College of Engineering · Semester 4 · Even Sem 2025-26
 * Classroom: CSE-CC 203
 *
 * Drop this file into:  web-dashboard/src/config/timetable.ts
 */

// ─── Types ───────────────────────────────────────────────────────────────────

export type DayCode = 'MON' | 'TUE' | 'WED' | 'THU' | 'FRI';

export interface Period {
  id: string;
  day: DayCode;
  dayFull: string;
  time: string;
  subject: string;   // Short abbreviation used in the timetable
  code: string;      // Course code
  course: string;    // Full course name
  faculty: string;
  email: string;
  totalStudents: number;
  isLab: boolean;
  /** Last 7 historical attendance percentages (oldest → newest) */
  trendBase: [number, number, number, number, number, number, number];
}

// ─── Section Info ─────────────────────────────────────────────────────────────

export const SECTION_INFO = {
  college:    'RV College of Engineering',
  program:    'Computer Science and Engineering',
  ugLevel:    'UG',
  department: 'CSE',
  section:    '4C',
  sectionLabel: 'C',
  semester:   4,
  classroom:  'CSE-CC 203',
  batch:      '2025-26',
  semType:    'EVEN SEM',
  wef:        '09.03.2026',
} as const;

// ─── All 22 Periods ───────────────────────────────────────────────────────────

export const PERIODS: Period[] = [
  // ── Monday ──────────────────────────────────────────────────────────────────
  {
    id: 'mon_iot', day: 'MON', dayFull: 'Monday', time: '09:00–10:00',
    subject: 'IOT', code: 'CS344AI',
    course: 'IoT and Embedded Computing',
    faculty: 'Prof. Neethu Srikumaran', email: 'neethus@rvce.edu.in',
    totalStudents: 60, isLab: false,
    trendBase: [78, 82, 75, 80, 77, 83, 79],
  },
  {
    id: 'mon_daa', day: 'MON', dayFull: 'Monday', time: '10:00–11:00',
    subject: 'DAA', code: 'CD343AI',
    course: 'Design & Analysis of Algorithms',
    faculty: 'Prof. Saraswathi G Datar', email: 'saraswathigd@rvce.edu.in',
    totalStudents: 60, isLab: false,
    trendBase: [85, 82, 88, 84, 87, 83, 86],
  },
  {
    id: 'mon_dms', day: 'MON', dayFull: 'Monday', time: '11:30–12:30',
    subject: 'DMS', code: 'CS241AT',
    course: 'Discrete Mathematical Structures & Combinatorics',
    faculty: 'Dr. Anitha Sandeep', email: 'anithasandeep@rvce.edu.in',
    totalStudents: 60, isLab: false,
    trendBase: [72, 68, 74, 70, 73, 69, 71],
  },
  {
    id: 'mon_cn', day: 'MON', dayFull: 'Monday', time: '12:30–1:30',
    subject: 'CN', code: 'CY245AT',
    course: 'Computer Networks',
    faculty: 'Dr. G S Nagaraja', email: 'nagarajaGS@rvce.edu.in',
    totalStudents: 60, isLab: false,
    trendBase: [80, 77, 82, 79, 81, 78, 80],
  },
  {
    id: 'mon_bsk', day: 'MON', dayFull: 'Monday', time: '2:30–4:30',
    subject: 'BASKET', code: 'CS246TX',
    course: 'Professional Elective Course – Group B',
    faculty: '—', email: '—',
    totalStudents: 60, isLab: false,
    trendBase: [65, 68, 62, 66, 70, 64, 67],
  },

  // ── Tuesday ──────────────────────────────────────────────────────────────────
  {
    id: 'tue_daa', day: 'TUE', dayFull: 'Tuesday', time: '09:00–10:00',
    subject: 'DAA', code: 'CD343AI',
    course: 'Design & Analysis of Algorithms',
    faculty: 'Prof. Saraswathi G Datar', email: 'saraswathigd@rvce.edu.in',
    totalStudents: 60, isLab: false,
    trendBase: [88, 85, 90, 86, 89, 84, 87],
  },
  {
    id: 'tue_bsk', day: 'TUE', dayFull: 'Tuesday', time: '10:00–11:00',
    subject: 'BASKET', code: 'CS246TX',
    course: 'Professional Elective Course – Group B',
    faculty: '—', email: '—',
    totalStudents: 60, isLab: false,
    trendBase: [62, 65, 60, 64, 68, 61, 63],
  },
  {
    id: 'tue_cn', day: 'TUE', dayFull: 'Tuesday', time: '11:30–12:30',
    subject: 'CN', code: 'CY245AT',
    course: 'Computer Networks',
    faculty: 'Dr. G S Nagaraja', email: 'nagarajaGS@rvce.edu.in',
    totalStudents: 60, isLab: false,
    trendBase: [78, 81, 76, 80, 79, 77, 80],
  },
  {
    id: 'tue_iot', day: 'TUE', dayFull: 'Tuesday', time: '12:30–1:30',
    subject: 'IOT', code: 'CS344AI',
    course: 'IoT and Embedded Computing',
    faculty: 'Prof. Neethu Srikumaran', email: 'neethus@rvce.edu.in',
    totalStudents: 60, isLab: false,
    trendBase: [75, 79, 73, 77, 76, 74, 78],
  },
  {
    id: 'tue_aec', day: 'TUE', dayFull: 'Tuesday', time: '2:30–4:30',
    subject: 'AEC', code: 'HS247LX',
    course: 'Ability Enhancement Course – Group C',
    faculty: '—', email: '—',
    totalStudents: 60, isLab: false,
    trendBase: [55, 58, 52, 57, 60, 54, 56],
  },

  // ── Wednesday ─────────────────────────────────────────────────────────────────
  {
    id: 'wed_dms', day: 'WED', dayFull: 'Wednesday', time: '09:00–10:00',
    subject: 'DMS', code: 'CS241AT',
    course: 'Discrete Mathematical Structures & Combinatorics',
    faculty: 'Dr. Anitha Sandeep', email: 'anithasandeep@rvce.edu.in',
    totalStudents: 60, isLab: false,
    trendBase: [70, 73, 68, 71, 74, 69, 72],
  },
  {
    id: 'wed_cn', day: 'WED', dayFull: 'Wednesday', time: '10:00–11:00',
    subject: 'CN', code: 'CY245AT',
    course: 'Computer Networks',
    faculty: 'Dr. G S Nagaraja', email: 'nagarajaGS@rvce.edu.in',
    totalStudents: 60, isLab: false,
    trendBase: [82, 79, 84, 80, 83, 78, 81],
  },
  {
    id: 'wed_iot', day: 'WED', dayFull: 'Wednesday', time: '11:30–12:30',
    subject: 'IOT', code: 'CS344AI',
    course: 'IoT and Embedded Computing',
    faculty: 'Prof. Neethu Srikumaran', email: 'neethus@rvce.edu.in',
    totalStudents: 60, isLab: false,
    trendBase: [80, 77, 82, 79, 81, 76, 79],
  },
  {
    id: 'wed_el', day: 'WED', dayFull: 'Wednesday', time: '12:30–1:30',
    subject: 'EL', code: 'CV242AT',
    course: 'Environment & Sustainability (EL)',
    faculty: '—', email: '—',
    totalStudents: 60, isLab: false,
    trendBase: [58, 62, 55, 60, 63, 57, 59],
  },
  {
    id: 'wed_bcm', day: 'WED', dayFull: 'Wednesday', time: '2:30–4:30',
    subject: 'BCM', code: 'MAT149AT',
    course: 'Bridge Course: Mathematics',
    faculty: '—', email: '—',
    totalStudents: 60, isLab: false,
    trendBase: [68, 65, 70, 66, 69, 64, 67],
  },

  // ── Thursday ─────────────────────────────────────────────────────────────────
  {
    id: 'thu_lab', day: 'THU', dayFull: 'Thursday', time: '09:00–11:00',
    subject: 'IOT LAB', code: 'CS344AI',
    course: 'IoT Lab (2 hr)',
    faculty: 'Prof. Neethu Srikumaran', email: 'neethus@rvce.edu.in',
    totalStudents: 60, isLab: true,
    trendBase: [88, 85, 90, 87, 89, 84, 88],
  },
  {
    id: 'thu_uhv', day: 'THU', dayFull: 'Thursday', time: '11:30–12:30',
    subject: 'UHV', code: 'HS248AT',
    course: 'Universal Human Values',
    faculty: 'Prof. Ravikiran S wali', email: 'ravikiransw@rvce.edu.in',
    totalStudents: 60, isLab: false,
    trendBase: [60, 63, 57, 61, 65, 59, 62],
  },
  {
    id: 'thu_dms', day: 'THU', dayFull: 'Thursday', time: '12:30–1:30',
    subject: 'DMS*', code: 'CS241AT',
    course: 'Discrete Mathematical Structures – Extra Session',
    faculty: 'Dr. Anitha Sandeep', email: 'anithasandeep@rvce.edu.in',
    totalStudents: 60, isLab: false,
    trendBase: [74, 71, 76, 73, 77, 70, 74],
  },

  // ── Friday ────────────────────────────────────────────────────────────────────
  {
    id: 'fri_lab', day: 'FRI', dayFull: 'Friday', time: '09:00–11:00',
    subject: 'DAA LAB', code: 'CD343AI',
    course: 'DAA Lab (2 hr)',
    faculty: 'Prof. Saraswathi G Datar', email: 'saraswathigd@rvce.edu.in',
    totalStudents: 60, isLab: true,
    trendBase: [92, 89, 94, 91, 93, 88, 92],
  },
  {
    id: 'fri_uhv', day: 'FRI', dayFull: 'Friday', time: '11:30–12:30',
    subject: 'UHV', code: 'HS248AT',
    course: 'Universal Human Values',
    faculty: 'Prof. Ravikiran S wali', email: 'ravikiransw@rvce.edu.in',
    totalStudents: 60, isLab: false,
    trendBase: [58, 61, 56, 60, 63, 57, 59],
  },
  {
    id: 'fri_dms', day: 'FRI', dayFull: 'Friday', time: '12:30–1:30',
    subject: 'DMS', code: 'CS241AT',
    course: 'Discrete Mathematical Structures & Combinatorics',
    faculty: 'Dr. Anitha Sandeep', email: 'anithasandeep@rvce.edu.in',
    totalStudents: 60, isLab: false,
    trendBase: [72, 69, 74, 71, 75, 68, 72],
  },
  {
    id: 'fri_daa', day: 'FRI', dayFull: 'Friday', time: '2:30–3:30',
    subject: 'DAA', code: 'CD343AI',
    course: 'Design & Analysis of Algorithms',
    faculty: 'Prof. Saraswathi G Datar', email: 'saraswathigd@rvce.edu.in',
    totalStudents: 60, isLab: false,
    trendBase: [85, 82, 87, 84, 86, 81, 84],
  },
];

// ─── 60 Student Names (Section C) ─────────────────────────────────────────────

export const STUDENT_NAMES: string[] = [
  'Aisha Khan', 'Rohan Mehta', 'Priya Sharma', 'Dev Patel', 'Anjali Singh',
  'Vikram Nair', 'Shreya Gupta', 'Arjun Kumar', 'Neha Joshi', 'Karan Verma',
  'Sonal Rao', 'Aditya Sinha', 'Kavya Reddy', 'Manish Shah', 'Pooja Iyer',
  'Rahul Das', 'Sneha Pillai', 'Amit Chatterjee', 'Divya Menon', 'Suresh Tiwari',
  'Riya Bose', 'Nikhil Choudhury', 'Ananya Patel', 'Suraj Nayak', 'Meera Krishnan',
  'Sameer Ali', 'Tanvi Desai', 'Varun Malhotra', 'Ishaan Kapoor', 'Deepa Rao',
  'Akash Jain', 'Nidhi Saxena', 'Siddharth Ghosh', 'Lalitha Bhatt', 'Rohit Dubey',
  'Anushka Yadav', 'Kiran Pandey', 'Raj Thakur', 'Simran Kohli', 'Naveen Murthy',
  'Pooja Srivastava', 'Aryan Bansal', 'Ritu Agarwal', 'Mohit Mishra', 'Srishti Kaur',
  'Tarun Mathur', 'Shruti Sharma', 'Gaurav Bhatnagar', 'Nisha Datta', 'Yash Tomar',
  'Puja Tripathi', 'Arun Venkat', 'Divyesh Joshi', 'Richa Gupta', 'Omkar Patil',
  'Radhika Singh', 'Chirag Mehta', 'Deepika Kumar', 'Sanjay Patel', 'Shivani Agarwal',
];

// ─── Helpers ───────────────────────────────────────────────────────────────────

const DAY_INDEX: Record<DayCode, number> = { MON: 1, TUE: 2, WED: 3, THU: 4, FRI: 5 };

/**
 * Returns the last `count` dates on which a given day code fell.
 * E.g. getPastSessionDates('FRI', 7) → ['Mar 27', 'Apr 3', ..., 'May 8']
 */
export function getPastSessionDates(day: DayCode, count = 7): string[] {
  const target = DAY_INDEX[day];
  const dates: string[] = [];
  const d = new Date();
  while (dates.length < count) {
    d.setDate(d.getDate() - 1);
    if (d.getDay() === target) {
      dates.unshift(d.toLocaleDateString([], { month: 'short', day: 'numeric' }));
    }
  }
  return dates;
}

/**
 * Groups PERIODS by their full day name for use in <optgroup>.
 */
export function getPeriodsByDay(): Record<string, Period[]> {
  const order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
  const grouped: Record<string, Period[]> = {};
  order.forEach(d => { grouped[d] = []; });
  PERIODS.forEach(p => { grouped[p.dayFull].push(p); });
  return grouped;
}

/**
 * Find a single period by id. Throws if not found.
 */
export function getPeriodById(id: string): Period {
  const p = PERIODS.find(p => p.id === id);
  if (!p) throw new Error(`Period '${id}' not found in timetable`);
  return p;
}