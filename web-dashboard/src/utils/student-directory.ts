const STUDENT_DISPLAY_NAMES: Record<string, string> = {
  'stud_005': 'Pranav Kumar M',
  'stud_006': 'Nischith G A',
  'stud_007': 'Yohith N',
  'stud_008': 'Mahesh Raju N',
  'stud__006': 'Nischith G A',
  'stud__08': 'Mahesh Raju N',
  // Add more students as needed - can be extended dynamically
};

export function getStudentDisplayName(studentId?: string | null, fallback?: string): string {
  if (!studentId) return fallback ?? 'Unknown';

  const normalizedId = studentId.trim().toLowerCase();
  
  // First try exact match
  if (STUDENT_DISPLAY_NAMES[normalizedId]) {
    return STUDENT_DISPLAY_NAMES[normalizedId];
  }
  
  // Try without underscores
  const noUnderscores = normalizedId.replace(/_/g, '');
  for (const [key, value] of Object.entries(STUDENT_DISPLAY_NAMES)) {
    if (key.replace(/_/g, '') === noUnderscores) {
      return value;
    }
  }
  
  // Return fallback (which might be the student name from API response)
  return fallback ?? normalizedId.toUpperCase();
}
