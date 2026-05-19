import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import useRealtimeChannel, { EventEnvelope } from "./useRealtimeChannel";
import { getStoredAssignedSections, getStoredClassId } from "../services/firebase/auth.service";
import { getStoredRole } from "../utils/roles";

type SectionMap = Record<string, number>;

export default function useTeacherRealtime(opts: { clientId: string; token?: string; urlBase?: string }) {
  const { clientId, token, urlBase = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000') } = opts;
  const role = getStoredRole();
  const sectionId = useMemo(() => {
    if (role === 'admin') return 'ADMIN_GLOBAL';
    const assigned = getStoredAssignedSections();
    if (assigned.length > 0) return assigned[0];
    return getStoredClassId() || 'ADMIN_GLOBAL';
  }, [role]);
  const [authorizedSections, setAuthorizedSections] = useState<Set<string>>(new Set());
  const [unreadBySection, setUnreadBySection] = useState<SectionMap>({});
  const latestRef = useRef<Record<string, EventEnvelope[]>>({});

  const handleEvent = useCallback((env: EventEnvelope) => {
    if (env.event === "connected" || env.event === "pong") return;
    const sid = env.section_id || sectionId || "global";
    latestRef.current[sid] = latestRef.current[sid] || [];
    latestRef.current[sid].unshift(env);
    setUnreadBySection((prev) => ({ ...(prev || {}), [sid]: (prev[sid] || 0) + 1 }));
  }, [sectionId]);

  const { connected, protocol, reconnects } = useRealtimeChannel({ clientId, sectionId, role: role || "viewer", token, urlBase, onEvent: handleEvent });

  useEffect(() => {
    // clear entries for sections no longer authorized
    setUnreadBySection((prev) => {
      const out: SectionMap = {};
      Object.keys(prev).forEach((k) => { if (authorizedSections.has(k)) out[k] = prev[k]; });
      return out;
    });
  }, [authorizedSections]);

  const clearSection = useCallback((sectionId: string) => {
    setUnreadBySection((prev) => { const p = { ...(prev || {}) }; delete p[sectionId]; return p; });
    if (latestRef.current[sectionId]) latestRef.current[sectionId] = [];
  }, []);

  const totalUnread = Object.values(unreadBySection).reduce((s, n) => s + (n || 0), 0);

  return {
    connected, protocol, reconnects,
    authorizedSections,
    unreadBySection,
    latestBySection: latestRef.current,
    totalUnread,
    clearSection,
  };
}
