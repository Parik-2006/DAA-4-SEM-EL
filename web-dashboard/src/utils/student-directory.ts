// Cache for dynamically loaded student directory
let studentDirectoryCache: Record<string, { name: string; email?: string }> | null = null;

interface StudentInfo {
  name: string;
  email?: string;
}

function normalizeStudentKey(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]/g, '');
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
    const roster = await apiClient.getClassRoster(classId);
    
    const directory: Record<string, StudentInfo> = {};
    roster.forEach((student) => {
      const normalizedId = student.student_id.trim().toLowerCase();
      directory[normalizedId] = {
        name: student.name,
        email: student.email,
      };

      const compactId = normalizeStudentKey(normalizedId);
      directory[compactId] = {
        name: student.name,
        email: student.email,
      };

      if (student.email) {
        const normalizedEmail = student.email.trim().toLowerCase();
        directory[normalizedEmail] = {
          name: student.name,
          email: student.email,
        };
        directory[normalizeStudentKey(normalizedEmail)] = {
          name: student.name,
          email: student.email,
        };
      }
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
  };

  // Try exact match in hardcoded
  if (STUDENT_DISPLAY_NAMES[normalizedId]) {
    return { name: STUDENT_DISPLAY_NAMES[normalizedId] };
  }

  if (STUDENT_DISPLAY_NAMES[compactId]) {
    return { name: STUDENT_DISPLAY_NAMES[compactId] };
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
