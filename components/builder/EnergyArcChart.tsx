"use client";

import { Track } from "@/types";
import { getEnergyColor } from "@/lib/utils";
import { getCompatibility, getCompatibilityColor } from "@/lib/camelot";

interface EnergyArcChartProps {
  tracks: Track[];
}

export function EnergyArcChart({ tracks }: EnergyArcChartProps) {
  if (tracks.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-muted">
        Add tracks to see the energy arc
      </div>
    );
  }

  const width = 700;
  const height = 220;
  const pad = { top: 25, right: 30, bottom: 50, left: 45 };
  const chartW = width - pad.left - pad.right;
  const chartH = height - pad.top - pad.bottom;

  const points = tracks.map((t, i) => ({
    x: pad.left + (i / Math.max(tracks.length - 1, 1)) * chartW,
    y: pad.top + chartH - (t.energy / 10) * chartH,
    track: t,
  }));

  // Smooth curve
  const pathD = points.reduce((acc, p, i) => {
    if (i === 0) return `M ${p.x} ${p.y}`;
    const prev = points[i - 1];
    const cpx = (prev.x + p.x) / 2;
    return `${acc} C ${cpx} ${prev.y}, ${cpx} ${p.y}, ${p.x} ${p.y}`;
  }, "");

  const fillD = `${pathD} L ${points[points.length - 1].x} ${pad.top + chartH} L ${points[0].x} ${pad.top + chartH} Z`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
      <defs>
        <linearGradient id="arcGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#00f0ff" />
          <stop offset="50%" stopColor="#a855f7" />
          <stop offset="100%" stopColor="#ff00aa" />
        </linearGradient>
        <linearGradient id="arcFill" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#a855f7" stopOpacity={0.2} />
          <stop offset="100%" stopColor="#a855f7" stopOpacity={0} />
        </linearGradient>
      </defs>

      {/* Grid */}
      {[2, 4, 6, 8, 10].map((e) => {
        const y = pad.top + chartH - (e / 10) * chartH;
        return (
          <g key={e}>
            <line
              x1={pad.left}
              y1={y}
              x2={pad.left + chartW}
              y2={y}
              stroke="rgba(255,255,255,0.04)"
              strokeDasharray="3 3"
            />
            <text x={pad.left - 10} y={y + 3} textAnchor="end" fill="#666" fontSize="9">
              {e}
            </text>
          </g>
        );
      })}

      {/* Key compatibility connectors */}
      {points.slice(0, -1).map((p, i) => {
        const next = points[i + 1];
        const compat = getCompatibility(
          p.track.camelotCode,
          next.track.camelotCode
        );
        const color = getCompatibilityColor(compat);
        const midX = (p.x + next.x) / 2;
        const midY = pad.top + chartH + 6;
        return (
          <g key={i}>
            <line
              x1={p.x}
              y1={pad.top + chartH + 6}
              x2={next.x}
              y2={pad.top + chartH + 6}
              stroke={color}
              strokeWidth={2}
              opacity={0.6}
            />
            <circle cx={midX} cy={midY} r={3} fill={color} />
          </g>
        );
      })}

      {/* Fill + Line */}
      <path d={fillD} fill="url(#arcFill)" />
      <path d={pathD} fill="none" stroke="url(#arcGrad)" strokeWidth="2.5" />

      {/* Points + Labels */}
      {points.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r={6} fill={getEnergyColor(p.track.energy)} />
          <circle cx={p.x} cy={p.y} r={3} fill="#050505" />
          <text
            x={p.x}
            y={pad.top + chartH + 22}
            textAnchor="middle"
            fill="#888"
            fontSize="7"
          >
            {p.track.title.length > 14
              ? p.track.title.slice(0, 14) + "…"
              : p.track.title}
          </text>
          <text
            x={p.x}
            y={pad.top + chartH + 34}
            textAnchor="middle"
            fill="#666"
            fontSize="7"
          >
            {p.track.bpm} · {p.track.camelotCode}
          </text>
        </g>
      ))}

      {/* Axis labels */}
      <text
        x={8}
        y={height / 2}
        textAnchor="middle"
        fill="#666"
        fontSize="9"
        transform={`rotate(-90 8 ${height / 2})`}
      >
        Energy
      </text>
    </svg>
  );
}
