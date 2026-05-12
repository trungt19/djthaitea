"use client";

import { Track } from "@/types";
import { getCompatibility, getCompatibilityColor } from "@/lib/camelot";

interface TransitionNotesProps {
  fromTrack: Track;
  toTrack: Track;
  note: string;
  onNoteChange: (note: string) => void;
}

export function TransitionNotes({
  fromTrack,
  toTrack,
  note,
  onNoteChange,
}: TransitionNotesProps) {
  const compat = getCompatibility(fromTrack.camelotCode, toTrack.camelotCode);
  const bpmDiff = Math.abs(fromTrack.bpm - toTrack.bpm);
  const energyDiff = toTrack.energy - fromTrack.energy;

  return (
    <div className="mx-6 flex items-center gap-3 py-1">
      {/* Connector line */}
      <div className="flex flex-col items-center">
        <div className="h-4 w-px bg-border" />
        <div
          className="h-2 w-2 rounded-full"
          style={{ backgroundColor: getCompatibilityColor(compat) }}
        />
        <div className="h-4 w-px bg-border" />
      </div>

      {/* Transition info */}
      <div className="flex flex-1 items-center gap-3 rounded-md bg-surface-light px-3 py-1.5 text-xs">
        <span
          className="font-semibold"
          style={{ color: getCompatibilityColor(compat) }}
        >
          {compat === "perfect"
            ? "Perfect"
            : compat === "compatible"
              ? "Good"
              : "Clash"}
        </span>
        <span className="text-muted">
          {bpmDiff > 0 ? `${bpmDiff > 0 ? "+" : ""}${toTrack.bpm - fromTrack.bpm} BPM` : "Same BPM"}
        </span>
        <span className="text-muted">
          {energyDiff > 0
            ? `Energy +${energyDiff}`
            : energyDiff < 0
              ? `Energy ${energyDiff}`
              : "Same energy"}
        </span>
        <input
          type="text"
          value={note}
          onChange={(e) => onNoteChange(e.target.value)}
          placeholder="Transition note..."
          className="flex-1 bg-transparent text-foreground outline-none placeholder:text-muted/50"
        />
      </div>
    </div>
  );
}
