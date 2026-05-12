import { useState } from "react";
import {
  RefreshCw, Clock, Users, CheckCircle,
  XCircle, AlertTriangle, Activity, BarChart2, Search,
  Calendar, Wifi, WifiOff, BookOpen
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell
} from "recharts";

// ─── STATUS CONFIG (mirrors existing codebase) ───────────────────────────────
const STATUS_CONFIG = {
  present: { label: "Present", hex: "#22C55E", bg: "rgba(34,197,94,0.10)", border: "rgba(34,197,94,0.28)", icon: CheckCircle },
  absent:  { label: "Absent",  hex: "#EF4444", bg: "rgba(239,68,68,0.10)",  border: "rgba(239,68,68,0.28)",  icon: XCircle },
  late:    { label: "Late",    hex: "#F59E0B", bg: "rgba(245,158,11,0.10)", border: "rgba(245,158,11,0.28)", icon: Clock },
  pending: { label: "Pending", hex: "#94A3B8", bg: "rgba(148,163,184,0.10)",border: "rgba(148,163,184,0.22)",icon: Activity },
};

// ─── MOCK DATA ────────────────────────────────────────────────────────────────
const MOCK_CLASSES = [
  { id: "CSE-A-4SEM", label: "CSE A — 4th Sem", count: 62 },
  { id: "CSE-B-4SEM", label: "CSE B — 4th Sem", count: 58 },
  { id: "CSE-C-4SEM", label: "CSE C — 4th Sem", count: 61 },
  { id: "ISE-A-4SEM", label: "ISE A — 4th Sem", count: 54 },
];

const MOCK_STATS = { present: 38, absent: 12, late: 7, pending: 5 };

const MOCK_RECORDS = [
  { id: "1", roll: "1CS21CS001", name: "Parikshith B Bilchode", status: "present", time: "09:02", confidence: 0.97 },
  { id: "2", roll: "1CS21CS002", name: "Gagan D K",             status: "late",    time: "09:18", confidence: 0.91 },
  { id: "3", roll: "1CS21CS003", name: "Prajwal K",             status: "present", time: "08:58", confidence: 0.95 },
  { id: "4", roll: "1CS21CS004", name: "Ved U",                 status: "absent",  time: "—",     confidence: null },
  { id: "5", roll: "1CS21CS005", name: "Pranav Kumar M",        status: "present", time: "09:01", confidence: 0.89 },
  { id: "6", roll: "1CS21CS006", name: "Nischith G A",          status: "pending", time: "—",     confidence: null },
  { id: "7", roll: "1CS21CS007", name: "Aisha Sharma",          status: "present", time: "08:55", confidence: 0.98 },
  { id: "8", roll: "1CS21CS008", name: "Rohan Verma",           status: "late",    time: "09:22", confidence: 0.88 },
];

const MOCK_TREND = [
  { day: "Mon", present: 52, absent: 6, late: 4 },
  { day: "Tue", present: 48, absent: 9, late: 5 },
  { day: "Wed", present: 55, absent: 4, late: 3 },
  { day: "Thu", present: 44, absent: 12, late: 6 },
  { day: "Fri", present: 50, absent: 7, late: 5 },
  { day: "Sat", present: 38, absent: 15, late: 9 },
  { day: "Today", present: 38, absent: 12, late: 7 },
];

// ─── SHARED CARD STYLE ────────────────────────────────────────────────────────
const card = {
  background: "rgba(254,252,248,0.88)",
  border: "1px solid rgba(190,160,118,0.22)",
  borderRadius: "18px",
  boxShadow: "0 4px 20px rgba(80,50,20,0.07)",
};

// ═══════════════════════════════════════════════════════════════════════════════
// 1. DashboardHeader
// Props: title, subtitle, lastSync, isOnline, onRefresh, isRefreshing
// ═══════════════════════════════════════════════════════════════════════════════
function DashboardHeader({ title, subtitle, lastSync, isOnline, onRefresh, isRefreshing }: any) {
  const [btnHover, setBtnHover] = useState(false);
  return (
    <div style={{
      ...card,
      padding: "20px 28px",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      flexWrap: "wrap",
      gap: "14px",
    }}>
      {/* Left — brand + title */}
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
          <div style={{
            width: "38px", height: "38px", borderRadius: "12px",
            background: "linear-gradient(135deg,#6366F1 0%,#818CF8 100%)",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 4px 14px #6366F140", flexShrink: 0,
          }}>
            <BarChart2 size={18} color="#fff" />
          </div>
          <h1 style={{
            fontSize: "1.35rem", fontWeight: 800, color: "#1e293b",
            margin: 0, letterSpacing: "-0.02em", lineHeight: 1,
          }}>
            {title}
          </h1>
        </div>
        {subtitle && (
          <p style={{ fontSize: "0.76rem", color: "#94a3b8", margin: "0 0 0 48px" }}>{subtitle}</p>
        )}
      </div>

      {/* Right — status chips + refresh */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
        {/* Online/Offline badge */}
        <div style={{
          display: "flex", alignItems: "center", gap: "6px",
          padding: "6px 12px", borderRadius: "99px",
          background: isOnline ? "rgba(34,197,94,0.10)" : "rgba(239,68,68,0.10)",
          border: `1px solid ${isOnline ? "rgba(34,197,94,0.30)" : "rgba(239,68,68,0.30)"}`,
        }}>
          {isOnline ? <Wifi size={13} color="#22C55E" /> : <WifiOff size={13} color="#EF4444" />}
          <span style={{
            fontSize: "0.72rem", fontWeight: 700,
            color: isOnline ? "#16A34A" : "#DC2626",
          }}>
            {isOnline ? "Online" : "Offline"}
          </span>
        </div>

        {/* Last sync pill */}
        {lastSync && (
          <div style={{
            display: "flex", alignItems: "center", gap: "5px",
            padding: "6px 12px", borderRadius: "99px",
            background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.20)",
          }}>
            <Clock size={12} color="#6366F1" />
            <span style={{ fontSize: "0.70rem", fontWeight: 600, color: "#6366F1", fontFamily: "monospace" }}>
              Synced {lastSync}
            </span>
          </div>
        )}

        {/* Refresh button */}
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          onMouseEnter={() => setBtnHover(true)}
          onMouseLeave={() => setBtnHover(false)}
          style={{
            display: "flex", alignItems: "center", gap: "7px",
            padding: "8px 16px", borderRadius: "11px",
            border: `1.5px solid ${btnHover ? "#6366F1" : "#e2e8f0"}`,
            background: btnHover ? "#EEF2FF" : "#fff",
            color: btnHover ? "#4338CA" : "#475569",
            cursor: isRefreshing ? "not-allowed" : "pointer",
            fontSize: "0.78rem", fontWeight: 700,
            boxShadow: "0 2px 6px rgba(0,0,0,0.04)",
            opacity: isRefreshing ? 0.65 : 1,
            transition: "all 0.18s ease",
          }}
        >
          <RefreshCw
            size={14}
            style={{ animation: isRefreshing ? "spin 0.9s linear infinite" : "none" }}
          />
          {isRefreshing ? "Syncing…" : "Refresh"}
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// 2. PeriodSelector
// Props: classes [{id, label, count}], selected, onChange
// ═══════════════════════════════════════════════════════════════════════════════
function PeriodSelector({ classes, selected, onChange }: any) {
  return (
    <div style={{ ...card, padding: "16px 22px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "7px", marginBottom: "12px" }}>
        <BookOpen size={14} color="#6366F1" />
        <span style={{
          fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.13em",
          textTransform: "uppercase", color: "#94a3b8",
        }}>
          Select Class Period
        </span>
      </div>

      {/* Segmented pills */}
      <div style={{ display: "flex", gap: "7px", flexWrap: "wrap" }}>
        {classes.map((cls: any) => {
          const active = cls.id === selected;
          return (
            <ClassPill key={cls.id} cls={cls} active={active} onClick={() => onChange(cls.id)} />
          );
        })}
      </div>
    </div>
  );
}

function ClassPill({ cls, active, onClick }: any) {
  const [hov, setHov] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        padding: "8px 14px", borderRadius: "10px",
        border: `1.5px solid ${active ? "#6366F1" : hov ? "#A5B4FC" : "#e2e8f0"}`,
        background: active ? "#EEF2FF" : hov ? "#F5F3FF" : "#fff",
        color: active ? "#4338CA" : hov ? "#4338CA" : "#64748b",
        fontSize: "0.78rem", fontWeight: active ? 700 : 500,
        cursor: "pointer", transition: "all 0.16s ease",
        display: "flex", alignItems: "center", gap: "7px",
      }}
    >
      <span>{cls.label}</span>
      <span style={{
        fontSize: "0.62rem", padding: "1px 6px", borderRadius: "99px",
        background: active ? "#6366F120" : "#f1f5f9",
        color: active ? "#6366F1" : "#94a3b8", fontWeight: 700,
      }}>
        {cls.count}
      </span>
    </button>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// 3. LiveStatsCard
// Props: stats {present,absent,late,pending}, total, pulsing
// ═══════════════════════════════════════════════════════════════════════════════
function LiveStatsCard({ stats, total, pulsing }: any) {
  const attended = (stats.present || 0) + (stats.late || 0);
  const pct = total > 0 ? ((attended / total) * 100).toFixed(1) : "0.0";
  const bandColor = parseFloat(pct) >= 85 ? "#22C55E" : parseFloat(pct) >= 75 ? "#F59E0B" : "#EF4444";

  return (
    <div style={{ ...card, padding: "20px 24px" }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center",
        justifyContent: "space-between", marginBottom: "18px", flexWrap: "wrap", gap: "8px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Activity size={15} color="#6366F1" />
          <span style={{ fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.13em", textTransform: "uppercase", color: "#94a3b8" }}>
            Live Stats
          </span>
          {pulsing && (
            <span style={{
              display: "inline-flex", alignItems: "center", gap: "4px",
              padding: "2px 8px", borderRadius: "99px",
              background: "rgba(239,68,68,0.10)",
              fontSize: "0.60rem", fontWeight: 700, color: "#DC2626",
            }}>
              <span style={{
                width: "5px", height: "5px", borderRadius: "50%",
                background: "#DC2626", animation: "pulse 1.4s infinite",
              }} />
              LIVE
            </span>
          )}
        </div>
        <span style={{
          padding: "4px 12px", borderRadius: "99px",
          background: `${bandColor}14`, border: `1px solid ${bandColor}38`,
          fontSize: "0.78rem", fontWeight: 800, color: bandColor, fontFamily: "monospace",
        }}>
          {pct}% present
        </span>
      </div>

      {/* KPI 2×2 grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
        {["present", "absent", "late", "pending"].map((key: any) => {
          const cfg = (STATUS_CONFIG as any)[key];
          const Icon = cfg.icon;
          const val = stats[key] || 0;
          const frac = total > 0 ? (val / total) * 100 : 0;
          return (
            <div key={key} style={{
              padding: "14px 16px", borderRadius: "14px",
              background: cfg.bg, border: `1.5px solid ${cfg.border}`,
              position: "relative", overflow: "hidden",
            }}>
              {/* Top color stripe */}
              <div style={{
                position: "absolute", top: 0, left: 0, right: 0, height: "3px",
                background: cfg.hex, borderRadius: "14px 14px 0 0",
              }} />
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                <div>
                  <p style={{
                    fontSize: "0.60rem", fontWeight: 700, letterSpacing: "0.12em",
                    textTransform: "uppercase", color: "#94a3b8", marginBottom: "7px",
                  }}>
                    {cfg.label}
                  </p>
                  <p style={{
                    fontSize: "2rem", fontWeight: 900, color: cfg.hex,
                    lineHeight: 1, fontFamily: "monospace",
                  }}>
                    {val}
                  </p>
                  <p style={{ fontSize: "0.66rem", color: "#94a3b8", marginTop: "4px" }}>
                    {frac.toFixed(0)}% of class
                  </p>
                </div>
                <div style={{
                  width: "34px", height: "34px", borderRadius: "10px",
                  background: `${cfg.hex}18`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <Icon size={17} color={cfg.hex} />
                </div>
              </div>
              {/* Mini progress */}
              <div style={{
                height: "4px", borderRadius: "99px",
                background: "#e2e8f080", marginTop: "10px", overflow: "hidden",
              }}>
                <div style={{
                  height: "100%", width: `${Math.min(100, frac)}%`,
                  background: cfg.hex, borderRadius: "99px",
                  transition: "width 0.8s ease",
                }} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Total strip */}
      <div style={{
        marginTop: "12px", padding: "10px 14px", borderRadius: "12px",
        background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.16)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <Users size={13} color="#6366F1" />
          <span style={{ fontSize: "0.75rem", color: "#475569", fontWeight: 600 }}>Total enrolled</span>
        </div>
        <span style={{ fontSize: "1rem", fontWeight: 800, color: "#6366F1", fontFamily: "monospace" }}>
          {total}
        </span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// 4. AttendanceRecordsTable
// Props: records [{id,roll,name,status,time,confidence}], searchable
// ═══════════════════════════════════════════════════════════════════════════════
function AttendanceRecordsTable({ records, searchable }: any) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const filtered = records.filter((r: any) => {
    const matchQ = !query ||
      r.name.toLowerCase().includes(query.toLowerCase()) ||
      r.roll.includes(query);
    const matchS = !statusFilter || r.status === statusFilter;
    return matchQ && matchS;
  });

  return (
    <div style={{ ...card, overflow: "hidden" }}>
      {/* Toolbar */}
      <div style={{
        padding: "14px 20px",
        borderBottom: "1px solid rgba(190,160,118,0.15)",
        display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", flex: 1 }}>
          <Users size={14} color="#6366F1" />
          <span style={{ fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: "#94a3b8" }}>
            Attendance Records
          </span>
          <span style={{
            fontSize: "0.62rem", padding: "2px 8px", borderRadius: "99px",
            background: "#EEF2FF", color: "#6366F1", fontWeight: 700,
          }}>
            {filtered.length}
          </span>
        </div>

        {/* Search */}
        {searchable && (
          <SearchInput value={query} onChange={setQuery} />
        )}

        {/* Status filter */}
        <div style={{ display: "flex", gap: "5px", flexWrap: "wrap" }}>
          {["", "present", "absent", "late", "pending"].map((s: any) => (
            <FilterPill
              key={s || "all"}
              label={s ? (STATUS_CONFIG as any)[s].label : "All"}
              active={statusFilter === s}
              hex={s ? (STATUS_CONFIG as any)[s].hex : "#6366F1"}
              bg={s ? (STATUS_CONFIG as any)[s].bg : "#EEF2FF"}
              onClick={() => setStatusFilter(s)}
            />
          ))}
        </div>
      </div>

      {/* Table scroll wrapper */}
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "rgba(248,250,252,0.85)" }}>
              {["Roll No", "Student", "Time", "Status", "Confidence"].map((h: any) => (
                <th key={h} style={{
                  padding: "9px 16px", textAlign: "left",
                  fontSize: "0.60rem", fontWeight: 700,
                  letterSpacing: "0.12em", textTransform: "uppercase", color: "#94a3b8",
                  borderBottom: "1px solid rgba(190,160,118,0.15)", whiteSpace: "nowrap",
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: "40px", textAlign: "center", color: "#94a3b8", fontSize: "0.82rem" }}>
                  No records match your filters
                </td>
              </tr>
            ) : (
              filtered.map((rec: any, i: any) => (
                <RecordRow key={rec.id} rec={rec} index={i} />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SearchInput({ value, onChange }: any) {
  const [focused, setFocused] = useState(false);
  return (
    <div style={{ position: "relative", minWidth: "200px" }}>
      <Search size={12} style={{
        position: "absolute", left: "10px", top: "50%",
        transform: "translateY(-50%)", color: "#94a3b8",
      }} />
      <input
        value={value}
        onChange={(e: any) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder="Search name or roll…"
        style={{
          paddingLeft: "28px", paddingRight: "10px", paddingTop: "7px", paddingBottom: "7px",
          borderRadius: "9px",
          border: `1.5px solid ${focused ? "#6366F1" : "#e2e8f0"}`,
          fontSize: "0.74rem", background: "#fff", color: "#1e293b",
          outline: "none", width: "100%", transition: "border-color 0.15s",
        }}
      />
    </div>
  );
}

function FilterPill({ label, active, hex, bg, onClick }: any) {
  const [hov, setHov] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        padding: "5px 10px", borderRadius: "8px",
        border: `1.5px solid ${active ? hex : hov ? hex + "80" : "#e2e8f0"}`,
        background: active ? bg : hov ? bg + "80" : "#fff",
        color: active ? hex : hov ? hex : "#64748b",
        fontSize: "0.68rem", fontWeight: 700,
        cursor: "pointer", transition: "all 0.15s",
      }}
    >
      {label}
    </button>
  );
}

function RecordRow({ rec, index }: any) {
  const [hov, setHov] = useState(false);
  const cfg = (STATUS_CONFIG as any)[rec.status] || (STATUS_CONFIG as any).pending;
  const Icon = cfg.icon;
  const initials = rec.name.split(" ").map((w: any) => w[0]).join("").slice(0, 2).toUpperCase();

  return (
    <tr
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        borderBottom: "1px solid rgba(190,160,118,0.10)",
        background: hov ? "rgba(248,250,252,0.95)" : index % 2 === 0 ? "#fff" : "rgba(250,251,255,0.6)",
        transition: "background 0.14s",
      }}
    >
      {/* Roll */}
      <td style={{
        padding: "10px 16px", fontSize: "0.70rem",
        fontFamily: "monospace", color: "#6366F1", fontWeight: 700, whiteSpace: "nowrap",
      }}>
        {rec.roll}
      </td>
      {/* Name + avatar */}
      <td style={{ padding: "10px 16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "9px" }}>
          <div style={{
            width: "28px", height: "28px", borderRadius: "50%", flexShrink: 0,
            background: `${cfg.hex}18`, border: `1.5px solid ${cfg.hex}35`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "0.58rem", fontWeight: 800, color: cfg.hex,
          }}>
            {initials}
          </div>
          <span style={{ fontSize: "0.80rem", fontWeight: 600, color: "#1e293b" }}>
            {rec.name}
          </span>
        </div>
      </td>
      {/* Time */}
      <td style={{
        padding: "10px 16px", fontSize: "0.74rem",
        fontFamily: "monospace",
        color: rec.time === "—" ? "#cbd5e1" : "#64748b",
        whiteSpace: "nowrap",
      }}>
        {rec.time !== "—" && (
          <Clock size={11} style={{ display: "inline", marginRight: "4px", verticalAlign: "middle", color: "#94a3b8" }} />
        )}
        {rec.time}
      </td>
      {/* Status badge */}
      <td style={{ padding: "10px 16px" }}>
        <span style={{
          display: "inline-flex", alignItems: "center", gap: "5px",
          padding: "3px 9px", borderRadius: "99px",
          background: cfg.bg, color: cfg.hex,
          fontSize: "0.67rem", fontWeight: 700,
          border: `1px solid ${cfg.border}`,
        }}>
          <Icon size={10} />
          {cfg.label}
        </span>
      </td>
      {/* Confidence */}
      <td style={{ padding: "10px 16px" }}>
        {rec.confidence != null ? (
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <div style={{
              width: "50px", height: "5px", borderRadius: "99px",
              background: "#e2e8f0", overflow: "hidden",
            }}>
              <div style={{
                height: "100%",
                width: `${rec.confidence * 100}%`,
                background: rec.confidence >= 0.9 ? "#22C55E" : rec.confidence >= 0.75 ? "#F59E0B" : "#EF4444",
                borderRadius: "99px",
              }} />
            </div>
            <span style={{ fontSize: "0.68rem", fontFamily: "monospace", color: "#64748b", fontWeight: 600 }}>
              {(rec.confidence * 100).toFixed(0)}%
            </span>
          </div>
        ) : (
          <span style={{ color: "#cbd5e1", fontSize: "0.75rem" }}>—</span>
        )}
      </td>
    </tr>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// 5. TrendSnapshot
// Props: data [{day,present,absent,late}], activeKey, onKeyChange
// ═══════════════════════════════════════════════════════════════════════════════
function TrendSnapshot({ data, activeKey, onKeyChange }: any) {
  const keys = ["present", "absent", "late"];

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    return (
      <div style={{
        background: "#1e293b", borderRadius: "11px", padding: "10px 14px",
        boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
      }}>
        <p style={{ fontSize: "0.67rem", color: "#94a3b8", marginBottom: "6px", fontWeight: 600 }}>
          {label}
        </p>
        {payload.map((p: any) => (
          <div key={p.dataKey} style={{
            display: "flex", alignItems: "center", gap: "8px", marginBottom: "3px",
          }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: p.fill || (STATUS_CONFIG as any)[p.dataKey]?.hex }} />
            <span style={{ fontSize: "0.75rem", color: "#e2e8f0", fontWeight: 600, textTransform: "capitalize" }}>
              {p.dataKey}: {p.value}
            </span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div style={{ ...card, padding: "20px 24px" }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        marginBottom: "16px", flexWrap: "wrap", gap: "10px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Calendar size={15} color="#6366F1" />
          <span style={{ fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.13em", textTransform: "uppercase", color: "#94a3b8" }}>
            7-Day Snapshot
          </span>
        </div>
        {/* Key toggle pills */}
        <div style={{ display: "flex", gap: "6px" }}>
          {keys.map((k: any) => {
            const cfg = (STATUS_CONFIG as any)[k];
            const active = activeKey === k;
            return (
              <TrendToggle
                key={k}
                label={cfg.label}
                hex={cfg.hex}
                bg={cfg.bg}
                active={active}
                onClick={() => onKeyChange && onKeyChange(active ? null : k)}
              />
            );
          })}
        </div>
      </div>

      {/* Bar chart */}
      <ResponsiveContainer width="100%" height={178}>
        <BarChart data={data} margin={{ top: 4, right: 4, left: -24, bottom: 0 }} barSize={16}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
          <XAxis
            dataKey="day"
            tick={{ fontSize: 11, fill: "#94a3b8", fontWeight: 600 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "#94a3b8" }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(99,102,241,0.05)", radius: 6 }} />
          {keys.map((k: any) => {
            const cfg = (STATUS_CONFIG as any)[k];
            const visible = !activeKey || activeKey === k;
            if (!visible) return null;
            return (
              <Bar key={k} dataKey={k} radius={[4, 4, 0, 0]} opacity={0.88}>
                {data.map((entry: any, idx: any) => (
                  <Cell
                    key={idx}
                    fill={entry.day === "Today" ? cfg.hex : cfg.hex + "99"}
                  />
                ))}
              </Bar>
            );
          })}
        </BarChart>
      </ResponsiveContainer>

      {/* Legend / totals */}
      <div style={{
        display: "flex", gap: "18px", justifyContent: "center",
        marginTop: "10px", paddingTop: "10px",
        borderTop: "1px solid rgba(190,160,118,0.13)",
      }}>
        {keys.map((k: any) => {
          const cfg = (STATUS_CONFIG as any)[k];
          const total = data.reduce((s: any, d: any) => s + (d[k] || 0), 0);
          return (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "10px", height: "10px", borderRadius: "3px", background: cfg.hex }} />
              <span style={{ fontSize: "0.70rem", color: "#64748b", fontWeight: 600 }}>{cfg.label}</span>
              <span style={{ fontSize: "0.62rem", fontFamily: "monospace", color: "#94a3b8" }}>
                Σ{total}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TrendToggle({ label, hex, bg, active, onClick }: any) {
  const [hov, setHov] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: "flex", alignItems: "center", gap: "5px",
        padding: "5px 10px", borderRadius: "8px",
        border: `1.5px solid ${active ? hex : hov ? hex + "80" : "#e2e8f0"}`,
        background: active ? bg : hov ? bg + "80" : "#fff",
        color: active ? hex : hov ? hex : "#64748b",
        fontSize: "0.68rem", fontWeight: 700,
        cursor: "pointer", transition: "all 0.15s",
      }}
    >
      <span style={{ width: "7px", height: "7px", borderRadius: "50%", background: hex }} />
      {label}
    </button>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// DEMO — wires everything together with mock data
// ═══════════════════════════════════════════════════════════════════════════════
export default function AttendanceDashboard() {
  const [selectedClass, setSelectedClass] = useState("CSE-A-4SEM");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [trendKey, setTrendKey] = useState(null);

  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => setIsRefreshing(false), 1800);
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(145deg, #FAF6ED 0%, #EEE8DC 100%)",
      padding: "24px 20px",
      fontFamily: "'DM Sans', system-ui, sans-serif",
    }}>
      <style>{`
        @keyframes spin   { to { transform: rotate(360deg); } }
        @keyframes pulse  { 0%,100% { opacity:1; } 50% { opacity:0.35; } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
      `}</style>

      <div style={{ maxWidth: "1080px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "14px" }}>

        {/* ① DashboardHeader */}
        <DashboardHeader
          title="Attendance Dashboard"
          subtitle="Smart Attendance System — AttendMate Command"
          lastSync="09:32 AM"
          isOnline={true}
          onRefresh={handleRefresh}
          isRefreshing={isRefreshing}
        />

        {/* ② PeriodSelector */}
        <PeriodSelector
          classes={MOCK_CLASSES}
          selected={selectedClass}
          onChange={setSelectedClass}
        />

        {/* ③ + ⑤  LiveStatsCard  &  TrendSnapshot */}
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(0,1.35fr)", gap: "14px" }}>
          <LiveStatsCard stats={MOCK_STATS} total={62} pulsing={true} />
          <TrendSnapshot data={MOCK_TREND} activeKey={trendKey} onKeyChange={setTrendKey} />
        </div>

        {/* ④ AttendanceRecordsTable */}
        <AttendanceRecordsTable records={MOCK_RECORDS} searchable={true} />

        {/* Export guide */}
        <div style={{
          ...card,
          padding: "14px 20px",
          background: "rgba(238,242,255,0.72)",
          border: "1px solid rgba(99,102,241,0.18)",
        }}>
          <p style={{ fontSize: "0.62rem", fontWeight: 700, color: "#6366F1", letterSpacing: "0.13em", textTransform: "uppercase", marginBottom: "10px" }}>
            Reusable Components (props-only, no data fetching)
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "7px" }}>
            {[
              ["DashboardHeader",       "title · subtitle · lastSync · isOnline · onRefresh · isRefreshing"],
              ["PeriodSelector",        "classes[] · selected · onChange"],
              ["LiveStatsCard",         "stats{} · total · pulsing"],
              ["TrendSnapshot",         "data[] · activeKey · onKeyChange"],
              ["AttendanceRecordsTable","records[] · searchable"],
            ].map(([name, props]: any) => (
              <div key={name} style={{
                padding: "7px 12px", borderRadius: "10px",
                background: "#fff", border: "1px solid rgba(99,102,241,0.22)",
              }}>
                <span style={{ fontSize: "0.72rem", fontFamily: "monospace", color: "#4338CA", fontWeight: 700 }}>
                  {"<"}{name}{" />"}
                </span>
                <span style={{ fontSize: "0.64rem", color: "#94a3b8", marginLeft: "8px" }}>{props}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
