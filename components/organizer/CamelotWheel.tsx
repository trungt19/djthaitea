"use client";

import { ALL_CAMELOT_CODES, CAMELOT_WHEEL, getCompatibleKeys } from "@/lib/camelot";
import { Track } from "@/types";

interface CamelotWheelProps {
  tracks: Track[];
  selectedCode: string | null;
  onSelect: (code: string) => void;
}

export function CamelotWheel({ tracks, selectedCode, onSelect }: CamelotWheelProps) {
  const compatible = selectedCode ? getCompatibleKeys(selectedCode) : [];

  // Arrange codes in wheel order: inner ring = A (minor), outer ring = B (major)
  const innerCodes = Array.from({ length: 12 }, (_, i) => `${i + 1}A`);
  const outerCodes = Array.from({ length: 12 }, (_, i) => `${i + 1}B`);

  function getSegmentColor(code: string) {
    if (selectedCode === code) return "#00f0ff";
    if (compatible.includes(code)) return "#39ff14";
    return "rgba(255,255,255,0.08)";
  }

  function getTextColor(code: string) {
    if (selectedCode === code) return "#00f0ff";
    if (compatible.includes(code)) return "#39ff14";
    return "#888";
  }

  const trackCountByCode: Record<string, number> = {};
  tracks.forEach((t) => {
    trackCountByCode[t.camelotCode] = (trackCountByCode[t.camelotCode] || 0) + 1;
  });

  const cx = 200;
  const cy = 200;

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 400 400" className="w-full max-w-[400px]">
        {/* Outer ring (Major / B) */}
        {outerCodes.map((code, i) => {
          const angle = (i * 30 - 90) * (Math.PI / 180);
          const r = 160;
          const x = cx + r * Math.cos(angle);
          const y = cy + r * Math.sin(angle);
          const count = trackCountByCode[code] || 0;

          return (
            <g key={code} onClick={() => onSelect(code)} className="cursor-pointer">
              <circle
                cx={x}
                cy={y}
                r={22}
                fill={getSegmentColor(code)}
                fillOpacity={selectedCode === code ? 0.3 : 0.1}
                stroke={getSegmentColor(code)}
                strokeWidth={selectedCode === code ? 2 : 1}
              />
              <text
                x={x}
                y={y - 4}
                textAnchor="middle"
                fill={getTextColor(code)}
                fontSize="11"
                fontWeight="bold"
                fontFamily="var(--font-space-grotesk)"
              >
                {code}
              </text>
              <text
                x={x}
                y={y + 8}
                textAnchor="middle"
                fill={getTextColor(code)}
                fontSize="8"
                opacity={0.7}
              >
                {CAMELOT_WHEEL[code].key}
              </text>
              {count > 0 && (
                <circle cx={x + 14} cy={y - 14} r={7} fill="#ff00aa" fillOpacity={0.9}>
                  <title>{count} track(s)</title>
                </circle>
              )}
              {count > 0 && (
                <text
                  x={x + 14}
                  y={y - 11}
                  textAnchor="middle"
                  fill="white"
                  fontSize="8"
                  fontWeight="bold"
                >
                  {count}
                </text>
              )}
            </g>
          );
        })}

        {/* Inner ring (Minor / A) */}
        {innerCodes.map((code, i) => {
          const angle = (i * 30 - 90) * (Math.PI / 180);
          const r = 100;
          const x = cx + r * Math.cos(angle);
          const y = cy + r * Math.sin(angle);
          const count = trackCountByCode[code] || 0;

          return (
            <g key={code} onClick={() => onSelect(code)} className="cursor-pointer">
              <circle
                cx={x}
                cy={y}
                r={22}
                fill={getSegmentColor(code)}
                fillOpacity={selectedCode === code ? 0.3 : 0.1}
                stroke={getSegmentColor(code)}
                strokeWidth={selectedCode === code ? 2 : 1}
              />
              <text
                x={x}
                y={y - 4}
                textAnchor="middle"
                fill={getTextColor(code)}
                fontSize="11"
                fontWeight="bold"
                fontFamily="var(--font-space-grotesk)"
              >
                {code}
              </text>
              <text
                x={x}
                y={y + 8}
                textAnchor="middle"
                fill={getTextColor(code)}
                fontSize="8"
                opacity={0.7}
              >
                {CAMELOT_WHEEL[code].key}m
              </text>
              {count > 0 && (
                <circle cx={x + 14} cy={y - 14} r={7} fill="#ff00aa" fillOpacity={0.9} />
              )}
              {count > 0 && (
                <text
                  x={x + 14}
                  y={y - 11}
                  textAnchor="middle"
                  fill="white"
                  fontSize="8"
                  fontWeight="bold"
                >
                  {count}
                </text>
              )}
            </g>
          );
        })}

        {/* Center label */}
        <text x={cx} y={cy - 6} textAnchor="middle" fill="#888" fontSize="10">
          CAMELOT
        </text>
        <text x={cx} y={cy + 8} textAnchor="middle" fill="#888" fontSize="10">
          WHEEL
        </text>
      </svg>

      {selectedCode && (
        <div className="mt-4 text-center text-sm">
          <span className="text-neon-cyan">{selectedCode}</span>
          <span className="text-muted"> — {CAMELOT_WHEEL[selectedCode].key} {CAMELOT_WHEEL[selectedCode].mode}</span>
          <div className="mt-1 text-xs text-muted">
            Compatible: {compatible.filter((c) => c !== selectedCode).join(", ")}
          </div>
        </div>
      )}
    </div>
  );
}
