/**
 * roles.ts — Single source of truth for user role classification.
 *
 * Priority order:
 *  1. Backend role (from login response) — authoritative
 *  2. Email whitelist — frontend guardrail / rejection gate
 *
 * The email check runs BEFORE any network call succeeds so an unknown
 * address is rejected immediately with a clear message.
 */

export type UserRole = 'admin' | 'teacher' | 'student';

// ── Hardcoded whitelists ───────────────────────────────────────────────────────

const ADMIN_EMAILS = new Set<string>([
  'raptorparik2006@gmail.com',
]);

const TEACHER_EMAILS = new Set<string>([
  'ganashree@rvce.edu.in',
  'nagarajags@rvce.edu.in',
  'saraswathigd@rvce.edu.in',
  'neethus@rvce.edu.in',
]);

const RVCE_DOMAIN = '@rvce.edu.in';

// ── Email-based role resolver (frontend guardrail) ────────────────────────────

/**
 * Classify a role purely from the email address.
 * Returns null if the email is not permitted to log in at all.
 *
 * Rules (evaluated top-to-bottom):
 *  • Exact match in ADMIN_EMAILS   → 'admin'
 *  • Exact match in TEACHER_EMAILS → 'teacher'
 *  • Any other *@rvce.edu.in       → 'student'
 *  • Anything else                 → null  (rejected)
 */
export function resolveRoleFromEmail(email: string): UserRole | null {
  const normalised = email.trim().toLowerCase();

  if (ADMIN_EMAILS.has(normalised)) return 'admin';
  if (TEACHER_EMAILS.has(normalised)) return 'teacher';
  if (normalised.endsWith(RVCE_DOMAIN)) return 'student';

  return null; // not authorised
}

// ── Backend-response role resolver ────────────────────────────────────────────

/**
 * Map the raw role string that the backend returns to our typed UserRole.
 * Falls back to the email-derived role when the backend sends nothing useful.
 */
function normaliseBackendRole(raw: string | undefined | null): UserRole | null {
  if (!raw) return null;
  const lower = raw.trim().toLowerCase();
  if (lower === 'admin')   return 'admin';
  if (lower === 'teacher' || lower === 'faculty') return 'teacher';
  if (lower === 'student') return 'student';
  return null;
}

// ── Primary resolver (call this after a successful login response) ─────────────

export interface ResolveRoleOptions {
  email: string;
  /** Raw role string from the backend login response (e.g. data.role) */
  backendRole?: string | null;
}

export interface RoleResolutionResult {
  role: UserRole;
  /** true when the email itself is not in any allowed category */
  rejected: boolean;
  /** Human-readable reason for rejection, set only when rejected === true */
  rejectionReason?: string;
}

/**
 * Resolve the final user role, using the backend as source of truth with the
 * email whitelist as a hard frontend guardrail.
 *
 * @example
 *   const result = resolveUserRole({ email, backendRole: data.role });
 *   if (result.rejected) throw new Error(result.rejectionReason);
 *   localStorage.setItem('user_role', result.role);
 */
export function resolveUserRole({
  email,
  backendRole,
}: ResolveRoleOptions): RoleResolutionResult {
  // Step 1 — Email guardrail: reject completely unknown addresses upfront.
  const emailRole = resolveRoleFromEmail(email);
  if (emailRole === null) {
    return {
      role: 'student', // unused, but satisfies the type
      rejected: true,
      rejectionReason:
        'Access denied. Only RVCE institutional accounts and authorised administrators may log in.',
    };
  }

  // Step 2 — Backend is authoritative when it sends a recognised role.
  const serverRole = normaliseBackendRole(backendRole);
  const finalRole: UserRole = serverRole ?? emailRole;

  return { role: finalRole, rejected: false };
}

// ── Convenience helpers ────────────────────────────────────────────────────────

/** Read the persisted role from sessionStorage (set at login). */
export function getStoredRole(): UserRole | null {
  const raw = sessionStorage.getItem('user_role');
  return (raw === 'admin' || raw === 'teacher' || raw === 'student') ? raw : null;
}

export const isAdmin   = (role: UserRole | null) => role === 'admin';
export const isTeacher = (role: UserRole | null) => role === 'teacher' || role === 'admin';
export const isStudent = (role: UserRole | null) => role === 'student';
