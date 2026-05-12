"use client";

import { useState, useMemo } from "react";
import { TrackCard } from "@/components/tracks/TrackCard";
import { TrackFilters } from "@/components/tracks/TrackFilters";
import { WaveformPlayer } from "@/components/audio/WaveformPlayer";
import { useAudio } from "@/components/audio/AudioProvider";
import { getAllTracks, getAllGenres } from "@/lib/tracks";
import { Track } from "@/types";
import { formatDuration, getEnergyColor } from "@/lib/utils";

export default function TracksPage() {
  const allTracks = getAllTracks();
  const genres = getAllGenres();
  const { currentTrack, isPlaying, toggle } = useAudio();

  const [selectedGenre, setSelectedGenre] = useState("");
  const [energyRange, setEnergyRange] = useState<[number, number]>([1, 10]);
  const [vocalsOnly, setVocalsOnly] = useState(false);
  const [sortBy, setSortBy] = useState<"bpm" | "energy" | "title" | "date">(
    "energy"
  );

  const filteredTracks = useMemo(() => {
    let tracks = allTracks;

    if (selectedGenre) {
      tracks = tracks.filter((t) => t.genres.includes(selectedGenre));
    }

    tracks = tracks.filter(
      (t) => t.energy >= energyRange[0] && t.energy <= energyRange[1]
    );

    if (vocalsOnly) {
      tracks = tracks.filter((t) => t.hasVocals);
    }

    switch (sortBy) {
      case "bpm":
        tracks = [...tracks].sort((a, b) => a.bpm - b.bpm);
        break;
      case "energy":
        tracks = [...tracks].sort((a, b) => a.energy - b.energy);
        break;
      case "title":
        tracks = [...tracks].sort((a, b) => a.title.localeCompare(b.title));
        break;
      case "date":
        tracks = [...tracks].sort(
          (a, b) =>
            new Date(b.dateAdded).getTime() - new Date(a.dateAdded).getTime()
        );
        break;
    }

    return tracks;
  }, [allTracks, selectedGenre, energyRange, vocalsOnly, sortBy]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-8">
        <h1 className="font-[family-name:var(--font-space-grotesk)] text-3xl font-bold tracking-tight text-glow-cyan text-neon-cyan">
          Tracks
        </h1>
        <p className="mt-2 text-muted">
          {filteredTracks.length} track{filteredTracks.length !== 1 && "s"} in
          library
        </p>
      </div>

      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <TrackFilters
          genres={genres}
          selectedGenre={selectedGenre}
          onGenreChange={setSelectedGenre}
          energyRange={energyRange}
          onEnergyChange={setEnergyRange}
          vocalsOnly={vocalsOnly}
          onVocalsChange={setVocalsOnly}
        />

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
          className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-foreground"
        >
          <option value="energy">Sort: Energy</option>
          <option value="bpm">Sort: BPM</option>
          <option value="title">Sort: Title</option>
          <option value="date">Sort: Date Added</option>
        </select>
      </div>

      <div className="flex flex-col gap-3">
        {filteredTracks.map((track) => {
          const active = currentTrack?.id === track.id;
          return (
            <div
              key={track.id}
              className={`rounded-lg border p-4 transition-all ${
                active
                  ? "border-neon-cyan/50 bg-neon-cyan/5 glow-cyan"
                  : "border-border bg-surface hover:bg-surface-light"
              }`}
            >
              <div className="flex items-center gap-4">
                {/* Play button */}
                <button
                  onClick={() => toggle(track)}
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-border bg-surface-lighter text-foreground transition-all hover:border-neon-cyan hover:text-neon-cyan"
                >
                  {active && isPlaying ? (
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 14 14"
                      fill="currentColor"
                    >
                      <rect x="2" y="1" width="4" height="12" rx="1" />
                      <rect x="8" y="1" width="4" height="12" rx="1" />
                    </svg>
                  ) : (
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 14 14"
                      fill="currentColor"
                    >
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
                <div className="hidden gap-1.5 md:flex">
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
                <div className="flex gap-0.5">
                  {Array.from({ length: 10 }, (_, i) => (
                    <div
                      key={i}
                      className="h-4 w-1 rounded-full"
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

              {/* Waveform (shown when active) */}
              {active && (
                <div className="mt-3">
                  <WaveformPlayer track={track} height={48} />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {filteredTracks.length === 0 && (
        <div className="py-20 text-center text-muted">
          <p className="text-lg">No tracks match your filters</p>
          <p className="mt-1 text-sm">Try adjusting the filters above</p>
        </div>
      )}
    </div>
  );
}
