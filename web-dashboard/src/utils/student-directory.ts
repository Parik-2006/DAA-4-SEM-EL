const STUDENT_DISPLAY_NAMES: Record<string, string> = {
  stud_005: 'Pranav Kumar M',
  stud__006: 'Nischith G A',
  stud_007: 'Yohith N',
  stud__08: 'Mahesh Raju N',
};

export function getStudentDisplayName(studentId?: string | null, fallback = 'Unknown'): string {
  if (!studentId) return fallback;

  const normalizedId = studentId.trim().toLowerCase();
  return STUDENT_DISPLAY_NAMES[normalizedId] ?? fallback;
}
