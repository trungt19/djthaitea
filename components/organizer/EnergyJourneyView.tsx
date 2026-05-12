"use client";

import { Track } from "@/types";
import { getEnergyColor } from "@/lib/utils";

interface EnergyJourneyViewProps {
  tracks: Track[];
}

export function EnergyJourneyView({ tracks }: EnergyJourneyViewProps) {
  if (tracks.length === 0) return null;

  const width = 600;
  const height = 200;
  const padding = { top: 20, right: 30, bottom: 40, left: 40 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  const points = tracks.map((t, i) => ({
    x: padding.left + (i / Math.max(tracks.length - 1, 1)) * chartW,
    y: padding.top + chartH - (t.energy / 10) * chartH,
    track: t,
  }));

  // Build smooth bezier path
  const pathD = points.reduce((acc, p, i) => {
    if (i === 0) return `M ${p.x} ${p.y}`;
    const prev = points[i - 1];
    const cpx = (prev.x + p.x) / 2;
    return `${acc} C ${cpx} ${prev.y}, ${cpx} ${p.y}, ${p.x} ${p.y}`;
  }, "");

  // Gradient fill path
  const fillD = `${pathD} L ${points[points.length - 1].x} ${padding.top + chartH} L ${points[0].x} ${padding.top + chartH} Z`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
      <defs>
        <linearGradient id="energyGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#00f0ff" />
          <stop offset="50%" stopColor="#a855f7" />
          <stop offset="100%" stopColor="#ff00aa" />
        </linearGradient>
        <linearGradient id="energyFill" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="url(#energyGradient)" stopOpacity={0.3} />
          <stop offset="100%" stopColor="url(#energyGradient)" stopOpacity={0} />
        </linearGradient>
      </defs>

      {/* Grid lines */}
      {[2, 4, 6, 8, 10].map((e) => {
        const y = padding.top + chartH - (e / 10) * chartH;
        return (
          <g key={e}>
            <line
              x1={padding.left}
              y1={y}
              x2={padding.left + chartW}
              y2={y}
              stroke="rgba(255,255,255,0.05)"
              strokeDasharray="4 4"
            />
            <text x={padding.left - 8} y={y + 4} textAnchor="end" fill="#888" fontSize="9">
              {e}
            </text>
          </g>
        );
      })}

      {/* Fill area */}
      <path d={fillD} fill="url(#energyFill)" />

      {/* Line */}
      <path d={pathD} fill="none" stroke="url(#energyGradient)" strokeWidth="2.5" />

      {/* Points */}
      {points.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r={5} fill={getEnergyColor(p.track.energy)} />
          <circle cx={p.x} cy={p.y} r={3} fill="#050505" />
          <text
            x={p.x}
            y={padding.top + chartH + 16}
            textAnchor="middle"
            fill="#888"
            fontSize="8"
          >
            {p.track.title.length > 12
              ? p.track.title.slice(0, 12) + "…"
              : p.track.title}
          </text>
        </g>
      ))}

      {/* Y-axis label */}
      <text
        x={10}
        y={height / 2}
        textAnchor="middle"
        fill="#888"
        fontSize="9"
        transform={`rotate(-90 10 ${height / 2})`}
      >
        Energy
      </text>
    </svg>
  );
}
