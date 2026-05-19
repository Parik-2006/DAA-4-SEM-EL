// Cache for dynamically loaded student directory
let studentDirectoryCache: Record<string, { name: string; email?: string }> | null = null;

interface StudentInfo {
  name: string;
  email?: string;
}

type StudentDirectoryEntry = { student_id: string; name: string; email?: string };

function normalizeStudentKey(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]/g, '');
}

const FALLBACK_STUDENT_ROSTER: StudentDirectoryEntry[] = [
  { student_id: 'student_001', name: 'Parikshith B Bilchode', email: 'parikshithbb.cs25@rvce.edu.in' },
  { student_id: 'STUD_001', name: 'Parikshith B Bilchode', email: 'parikshithbb.cs25@rvce.edu.in' },

  { student_id: 'student_002', name: 'Gagan D K', email: 'gagandk2005@gmail.com' },
  { student_id: 'STUD_002', name: 'Gagan D K', email: 'gagandk2005@gmail.com' },

  { student_id: 'student_003', name: 'Prajwal K', email: 'prajwalk.cs24@rvce.edu.in' },
  { student_id: 'STUD_003', name: 'Prajwal K', email: 'prajwalk.cs24@rvce.edu.in' },

  { student_id: 'student_004', name: 'Ved U', email: 'vedu.cs25@rvce.edu.in' },
  { student_id: 'STUD_004', name: 'Ved U', email: 'vedu.cs25@rvce.edu.in' },

  { student_id: 'student_005', name: 'Pranav Kumar M', email: 'pranavkumarm.cs24@rvce.edu.in' },
  { student_id: 'STUD_005', name: 'Pranav Kumar M', email: 'pranavkumarm.cs24@rvce.edu.in' },

  { student_id: 'student_006', name: 'Nischith G A', email: 'nishchithgarg.cs24@rvce.edu.in' },
  { student_id: 'STUD_006', name: 'Nischith G A', email: 'nishchithgarg.cs24@rvce.edu.in' },

  { student_id: 'student_007', name: 'Yohith N', email: 'nyohith.cs24@rvce.edu.in' },
  { student_id: 'STUD_007', name: 'Yohith N', email: 'nyohith.cs24@rvce.edu.in' },

  { student_id: 'student_008', name: 'Mahesh Raju', email: 'nrmaheshraju.cs24@rvce.edu.in' },
  { student_id: 'STUD_008', name: 'Mahesh Raju', email: 'nrmaheshraju.cs24@rvce.edu.in' },
];

function addStudentEntry(
  directory: Record<string, StudentInfo>,
  student: StudentDirectoryEntry
): void {
  const normalizedId = student.student_id.trim().toLowerCase();
  const compactId = normalizeStudentKey(normalizedId);

  directory[normalizedId] = { name: student.name, email: student.email };
  directory[compactId] = { name: student.name, email: student.email };

  if (student.email) {
    const normalizedEmail = student.email.trim().toLowerCase();
    directory[normalizedEmail] = { name: student.name, email: student.email };
    directory[normalizeStudentKey(normalizedEmail)] = { name: student.name, email: student.email };
  }
}

/**
 * Load student directory dynamically from the backend.
 * Returns a map of student_id -> { name, email }.
 */
export async function loadStudentDirectory(
  classId: string,
  apiClient: any // Avoid circular dependency - pass apiClient as param
): Promise<Record<string, StudentInfo>> {
  try {
    console.log(`[StudentDirectory] Loading roster for class: ${classId}`);
    const roster = (await apiClient.getClassRoster(classId)) as StudentDirectoryEntry[];
    
    const directory: Record<string, StudentInfo> = {};

    FALLBACK_STUDENT_ROSTER.forEach((student) => addStudentEntry(directory, student));

    roster.forEach((student) => {
      addStudentEntry(directory, student);
    });
    
    studentDirectoryCache = directory;
    console.log(`[StudentDirectory] Loaded ${roster.length} students`);
    return directory;
  } catch (err) {
    console.error('[StudentDirectory] Failed to load roster:', err);
    return studentDirectoryCache ?? {};
  }
}

/**
 * Get student info (name + email) by student ID.
 * Falls back to hardcoded names if dynamic load hasn't happened yet.
 */
export function getStudentInfo(studentId?: string | null): StudentInfo | null {
  if (!studentId) return null;

  const normalizedId = studentId.trim().toLowerCase();
  const compactId = normalizeStudentKey(normalizedId);

  // Try cache first (dynamically loaded)
  if (studentDirectoryCache && studentDirectoryCache[normalizedId]) {
    return studentDirectoryCache[normalizedId];
  }

  if (studentDirectoryCache && studentDirectoryCache[compactId]) {
    return studentDirectoryCache[compactId];
  }

  // Fallback to hardcoded for immediate use (especially on first load)
  const STUDENT_DISPLAY_NAMES: Record<string, string> = {
    'stud_005': 'Pranav Kumar M',
    'student_005': 'Pranav Kumar M',
    'stud005': 'Pranav Kumar M',
    'student005': 'Pranav Kumar M',
    'stud_006': 'Nischith G A',
    'student_006': 'Nischith G A',
    'stud006': 'Nischith G A',
    'student006': 'Nischith G A',
    'stud_007': 'Yohith N',
    'student_007': 'Yohith N',
    'stud_008': 'Mahesh Raju N',
    'student_008': 'Mahesh Raju N',
    'stud__006': 'Nischith G A',
    'stud__08': 'Mahesh Raju N',
    'student_001': 'Parikshith B Bilchode',
    'student001': 'Parikshith B Bilchode',
    'parik@example.com': 'Parikshith B Bilchode',
    'parikexamplecom': 'Parikshith B Bilchode',
  };

  // Try exact match in hardcoded
  if (STUDENT_DISPLAY_NAMES[normalizedId]) {
    return { name: STUDENT_DISPLAY_NAMES[normalizedId] };
  }

  if (STUDENT_DISPLAY_NAMES[compactId]) {
    return { name: STUDENT_DISPLAY_NAMES[compactId] };
  }

  // Last-chance fallback: check the static FALLBACK_STUDENT_ROSTER for name+email
  for (const entry of FALLBACK_STUDENT_ROSTER) {
    const entryNorm = entry.student_id.trim().toLowerCase();
    const entryCompact = normalizeStudentKey(entryNorm);
    if (entryNorm === normalizedId || entryCompact === compactId) {
      return { name: entry.name, email: entry.email };
    }
    // Also match by email string
    if (entry.email) {
      const emailNorm = entry.email.trim().toLowerCase();
      if (emailNorm === normalizedId || normalizeStudentKey(emailNorm) === compactId) {
        return { name: entry.name, email: entry.email };
      }
    }
  }

  // Try without underscores
  const noUnderscores = normalizedId.replace(/_/g, '');
  for (const [key, value] of Object.entries(STUDENT_DISPLAY_NAMES)) {
    if (key.replace(/[^a-z0-9]/g, '') === compactId || key.replace(/_/g, '') === noUnderscores) {
      return { name: value };
    }
  }

  return null;
}

/**
 * Get just the display name (for backwards compatibility).
 * Falls back to provided fallback or student ID in uppercase.
 */
export function getStudentDisplayName(studentId?: string | null, fallback?: string): string {
  const info = getStudentInfo(studentId);
  if (info?.name) return info.name;
  return fallback ?? (studentId ? studentId.toUpperCase() : 'Unknown');
}

/**
 * Get student email (returns empty string if not found).
 */
export function getStudentEmail(studentId?: string | null): string {
  const info = getStudentInfo(studentId);
  return info?.email ?? '';
}

export function findStudentByEmail(email?: string | null): { studentId: string; name: string; email?: string } | null {
  if (!email) return null;

  const normalizedEmail = email.trim().toLowerCase();
  const emailKey = normalizeStudentKey(normalizedEmail);

  for (const student of FALLBACK_STUDENT_ROSTER) {
    if (student.email?.trim().toLowerCase() === normalizedEmail) {
      return { studentId: student.student_id, name: student.name, email: student.email };
    }
  }

  if (studentDirectoryCache) {
    for (const [studentId, info] of Object.entries(studentDirectoryCache)) {
      const infoEmail = info.email?.trim().toLowerCase();
      if (!infoEmail) continue;
      if (infoEmail === normalizedEmail || normalizeStudentKey(infoEmail) === emailKey) {
        return { studentId, name: info.name, email: info.email };
      }
    }
  }

  return null;
}
