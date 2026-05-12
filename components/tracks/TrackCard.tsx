"use client";

import { Track } from "@/types";
import { formatDuration, getEnergyColor } from "@/lib/utils";

interface TrackCardProps {
  track: Track;
  onPlay?: (track: Track) => void;
  isPlaying?: boolean;
}

export function TrackCard({ track, onPlay, isPlaying }: TrackCardProps) {
  return (
    <div
      className={`group flex items-center gap-4 rounded-lg border p-4 transition-all ${
        isPlaying
          ? "border-neon-cyan/50 bg-neon-cyan/5 glow-cyan"
          : "border-border bg-surface hover:border-border hover:bg-surface-light"
      }`}
    >
      {/* Play button */}
      <button
        onClick={() => onPlay?.(track)}
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-border bg-surface-lighter text-foreground transition-all hover:border-neon-cyan hover:text-neon-cyan"
      >
        {isPlaying ? (
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
            <rect x="2" y="1" width="4" height="12" rx="1" />
            <rect x="8" y="1" width="4" height="12" rx="1" />
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
            <path d="M2 1.5v11l10-5.5z" />
          </svg>
        )}
      </button>

      {/* Track info */}
      <div className="min-w-0 flex-1">
        <h3 className="truncate font-[family-name:var(--font-space-grotesk)] font-semibold">
          {track.title}
        </h3>
        <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted">
          <span>{track.bpm} BPM</span>
          <span>
            {track.key}
            {track.keyMode === "minor" ? "m" : ""} ({track.camelotCode})
          </span>
          <span>{formatDuration(track.duration)}</span>
          {track.hasVocals && (
            <span className="text-neon-magenta">Vocals</span>
          )}
        </div>
      </div>

      {/* Genre tags */}
      <div className="hidden gap-1.5 sm:flex">
        {track.genres.map((genre) => (
          <span
            key={genre}
            className="rounded-full border border-border px-2 py-0.5 text-xs text-muted"
          >
            {genre}
          </span>
        ))}
      </div>

      {/* Energy bar */}
      <div className="flex items-center gap-2">
        <div className="flex gap-0.5">
          {Array.from({ length: 10 }, (_, i) => (
            <div
              key={i}
              className="h-4 w-1 rounded-full transition-all"
              style={{
                backgroundColor:
                  i < track.energy
                    ? getEnergyColor(track.energy)
                    : "rgba(255,255,255,0.05)",
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
