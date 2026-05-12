"use client";

import { useAudio } from "./AudioProvider";
import { formatDuration } from "@/lib/utils";
import { WaveformPlayer } from "./WaveformPlayer";

export function MiniPlayer() {
  const { currentTrack, isPlaying, currentTime, duration, pause, resume } =
    useAudio();

  if (!currentTrack) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-surface/95 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-2">
        {/* Play/Pause */}
        <button
          onClick={() => (isPlaying ? pause() : resume())}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-neon-cyan/30 text-neon-cyan transition-all hover:bg-neon-cyan/10"
        >
          {isPlaying ? (
            <svg
              width="12"
              height="12"
              viewBox="0 0 14 14"
              fill="currentColor"
            >
              <rect x="2" y="1" width="4" height="12" rx="1" />
              <rect x="8" y="1" width="4" height="12" rx="1" />
            </svg>
          ) : (
            <svg
              width="12"
              height="12"
              viewBox="0 0 14 14"
              fill="currentColor"
            >
              <path d="M2 1.5v11l10-5.5z" />
            </svg>
          )}
        </button>

        {/* Track info */}
        <div className="min-w-0 shrink-0">
          <div className="truncate font-[family-name:var(--font-space-grotesk)] text-sm font-semibold">
            {currentTrack.title}
          </div>
          <div className="text-xs text-muted">
            {currentTrack.bpm} BPM &middot; {currentTrack.key}
            {currentTrack.keyMode === "minor" ? "m" : ""}
          </div>
        </div>

        {/* Waveform */}
        <div className="flex-1">
          <WaveformPlayer track={currentTrack} height={36} />
        </div>

        {/* Time */}
        <div className="shrink-0 font-mono text-xs text-muted">
          {formatDuration(currentTime)} / {formatDuration(duration || currentTrack.duration)}
        </div>
      </div>
    </div>
  );
}
