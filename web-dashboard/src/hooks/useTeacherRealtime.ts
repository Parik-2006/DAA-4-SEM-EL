import { useCallback, useEffect, useRef, useState } from "react";
import useRealtimeChannel, { EventEnvelope } from "./useRealtimeChannel";

type SectionMap = Record<string, number>;

export default function useTeacherRealtime(opts: { clientId: string; token?: string; urlBase?: string }) {
  const { clientId, token, urlBase = "" } = opts;
  const [authorizedSections, setAuthorizedSections] = useState<Set<string>>(new Set());
  const [unreadBySection, setUnreadBySection] = useState<SectionMap>({});
  const latestRef = useRef<Record<string, EventEnvelope[]>>({});

  const handleEvent = useCallback((env: EventEnvelope) => {
    // handshake may include authorized_sections
    if (env.event === "handshake" && env.payload && env.payload.authorized_sections) {
      setAuthorizedSections(new Set(env.payload.authorized_sections || []));
      return;
    }

    const sid = env.section_id || "global";
    latestRef.current[sid] = latestRef.current[sid] || [];
    latestRef.current[sid].unshift(env);
    setUnreadBySection((prev) => ({ ...(prev || {}), [sid]: (prev[sid] || 0) + 1 }));
  }, []);

  const { connected, protocol, reconnects } = useRealtimeChannel({ clientId, role: "teacher", token, urlBase, onEvent: handleEvent });

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
