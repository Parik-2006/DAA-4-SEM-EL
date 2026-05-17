import React from "react";

type Props = { count?: number; onClick?: () => void; className?: string };

export default function ChannelBadge({ count = 0, onClick, className = "" }: Props) {
  if (!count) return null;
  return (
    <button onClick={onClick} className={`channel-badge ${className}`} title={`${count} new events`}>
      <span style={{ background: "#e53e3e", color: "white", borderRadius: 999, padding: "2px 6px", fontSize: 12 }}>
        {count}
      </span>
    </button>
  );
}
