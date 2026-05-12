"use client";

import { useRef, useCallback, useEffect, useState } from "react";
import { useAudio } from "./AudioProvider";
import { Track } from "@/types";

interface WaveformPlayerProps {
  track: Track;
  height?: number;
}

export function WaveformPlayer({ track, height = 60 }: WaveformPlayerProps) {
  const { currentTrack, isPlaying, currentTime, duration, toggle, seek } =
    useAudio();
  const containerRef = useRef<HTMLDivElement>(null);
  const [isClient, setIsClient] = useState(false);

  const isActive = currentTrack?.id === track.id;
  const progress = isActive && duration > 0 ? currentTime / duration : 0;

  useEffect(() => {
    setIsClient(true);
  }, []);

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!isActive || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width;
      seek(x * duration);
    },
    [isActive, duration, seek]
  );

  // Generate pseudo-waveform bars from track properties
  const barCount = 80;
  const bars = Array.from({ length: barCount }, (_, i) => {
    const seed = hashCode(`${track.id}-${i}`);
    const normalizedEnergy = track.energy / 10;
    const base = 0.15 + normalizedEnergy * 0.4;
    const variation = ((seed % 100) / 100) * 0.45;
    return base + variation;
  });

  if (!isClient) return null;

  return (
    <div
      ref={containerRef}
      className="cursor-pointer"
      style={{ height }}
      onClick={handleClick}
    >
      <div className="flex h-full items-end gap-[1px]">
        {bars.map((h, i) => {
          const barProgress = i / barCount;
          const isPast = isActive && barProgress <= progress;
          return (
            <div
              key={i}
              className="flex-1 rounded-t-sm transition-colors duration-75"
              style={{
                height: `${h * 100}%`,
                backgroundColor: isPast
                  ? "#00f0ff"
                  : isActive
                    ? "rgba(0, 240, 255, 0.15)"
                    : "rgba(255, 255, 255, 0.08)",
              }}
            />
          );
        })}
      </div>
    </div>
  );
}

function hashCode(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}
