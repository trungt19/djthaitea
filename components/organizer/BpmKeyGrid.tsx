"use client";

import { Track } from "@/types";
import { getEnergyColor } from "@/lib/utils";

interface BpmKeyGridProps {
  tracks: Track[];
}

export function BpmKeyGrid({ tracks }: BpmKeyGridProps) {
  // BPM ranges for rows
  const bpmRanges = [
    { label: "85-100", min: 85, max: 100 },
    { label: "100-115", min: 100, max: 115 },
    { label: "115-125", min: 115, max: 125 },
    { label: "125-135", min: 125, max: 135 },
    { label: "135-150", min: 135, max: 150 },
    { label: "150+", min: 150, max: 300 },
  ];

  // Camelot codes for columns
  const camelotCodes = Array.from({ length: 12 }, (_, i) => `${i + 1}A`);

  function getTracksInCell(bpmRange: { min: number; max: number }, code: string) {
    return tracks.filter(
      (t) => t.bpm >= bpmRange.min && t.bpm < bpmRange.max && t.camelotCode === code
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr>
            <th className="border border-border bg-surface-light px-2 py-2 text-left text-muted">
              BPM ↓ / Key →
            </th>
            {camelotCodes.map((code) => (
              <th
                key={code}
                className="border border-border bg-surface-light px-2 py-2 text-center text-muted"
              >
                {code}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bpmRanges.map((range) => (
            <tr key={range.label}>
              <td className="border border-border bg-surface-light px-2 py-2 font-mono text-muted">
                {range.label}
              </td>
              {camelotCodes.map((code) => {
                const cellTracks = getTracksInCell(range, code);
                return (
                  <td
                    key={code}
                    className="border border-border px-1 py-1 text-center"
                    title={cellTracks.map((t) => t.title).join(", ")}
                  >
                    {cellTracks.length > 0 ? (
                      <div className="flex flex-col items-center gap-1">
                        {cellTracks.map((t) => (
                          <div
                            key={t.id}
                            className="h-3 w-3 rounded-full"
                            style={{ backgroundColor: getEnergyColor(t.energy) }}
                            title={`${t.title} (E:${t.energy})`}
                          />
                        ))}
                      </div>
                    ) : (
                      <span className="text-border">·</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
