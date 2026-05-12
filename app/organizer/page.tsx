"use client";

import { useState } from "react";
import { getAllTracks } from "@/lib/tracks";
import { CamelotWheel } from "@/components/organizer/CamelotWheel";
import { BpmKeyGrid } from "@/components/organizer/BpmKeyGrid";
import { EnergyJourneyView } from "@/components/organizer/EnergyJourneyView";
import { getCompatibleKeys } from "@/lib/camelot";

export default function OrganizerPage() {
  const tracks = getAllTracks();
  const [selectedCamelot, setSelectedCamelot] = useState<string | null>(null);
  const [view, setView] = useState<"wheel" | "grid" | "journey">("wheel");

  const compatibleCodes = selectedCamelot
    ? getCompatibleKeys(selectedCamelot)
    : [];

  const filteredTracks = selectedCamelot
    ? tracks.filter((t) => compatibleCodes.includes(t.camelotCode))
    : tracks;

  // Sort by energy for journey view
  const journeyTracks = [...tracks].sort((a, b) => a.energy - b.energy);

  // Identify gaps in the library
  const usedCodes = new Set(tracks.map((t) => t.camelotCode));
  const bpmRange = {
    min: Math.min(...tracks.map((t) => t.bpm)),
    max: Math.max(...tracks.map((t) => t.bpm)),
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-8">
        <h1 className="font-[family-name:var(--font-space-grotesk)] text-3xl font-bold tracking-tight text-glow-cyan text-neon-cyan">
          Organizer
        </h1>
        <p className="mt-2 text-muted">
          Harmonic mixing tools, BPM analysis, and energy journey planning
        </p>
      </div>

      {/* View tabs */}
      <div className="mb-8 flex gap-2">
        {(["wheel", "grid", "journey"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              view === v
                ? "bg-neon-cyan/10 text-neon-cyan"
                : "text-muted hover:text-foreground"
            }`}
          >
            {v === "wheel"
              ? "Camelot Wheel"
              : v === "grid"
                ? "BPM/Key Grid"
                : "Energy Journey"}
          </button>
        ))}
      </div>

      {view === "wheel" && (
        <div className="grid gap-8 lg:grid-cols-2">
          <div>
            <CamelotWheel
              tracks={tracks}
              selectedCode={selectedCamelot}
              onSelect={(code) =>
                setSelectedCamelot(selectedCamelot === code ? null : code)
              }
            />
          </div>
          <div>
            <h3 className="font-[family-name:var(--font-space-grotesk)] font-semibold mb-4">
              {selectedCamelot
                ? `Compatible Tracks (${selectedCamelot})`
                : "All Tracks"}
            </h3>
            <div className="flex flex-col gap-2">
              {filteredTracks.map((track) => (
                <div
                  key={track.id}
                  className="flex items-center justify-between rounded-lg border border-border bg-surface p-3"
                >
                  <div>
                    <div className="font-[family-name:var(--font-space-grotesk)] text-sm font-semibold">
                      {track.title}
                    </div>
                    <div className="text-xs text-muted">
                      {track.bpm} BPM · {track.camelotCode} · Energy:{" "}
                      {track.energy}
                    </div>
                  </div>
                  <span className="rounded-full bg-surface-lighter px-2 py-0.5 text-xs text-neon-cyan">
                    {track.camelotCode}
                  </span>
                </div>
              ))}
              {filteredTracks.length === 0 && (
                <p className="py-8 text-center text-sm text-muted">
                  No tracks in this key — consider generating one!
                </p>
              )}
            </div>

            {/* Gap analysis */}
            <div className="mt-8 rounded-lg border border-border bg-surface p-4">
              <h3 className="font-[family-name:var(--font-space-grotesk)] text-sm font-semibold mb-3">
                Library Gaps
              </h3>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted">Keys covered</span>
                  <span>
                    {usedCodes.size}/24
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">BPM range</span>
                  <span>
                    {bpmRange.min}–{bpmRange.max}
                  </span>
                </div>
                <div className="mt-3">
                  <span className="text-muted">Missing intro/cooldown tracks:</span>
                  <div className="mt-1 text-neon-magenta">
                    {tracks.filter((t) => t.energy <= 4).length === 0
                      ? "Need tracks with energy 1-4 for intros/cooldowns"
                      : `${tracks.filter((t) => t.energy <= 4).length} low-energy track(s)`}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === "grid" && (
        <div>
          <p className="mb-4 text-sm text-muted">
            Each dot represents a track. Color indicates energy level.
            Hover for track details.
          </p>
          <BpmKeyGrid tracks={tracks} />
        </div>
      )}

      {view === "journey" && (
        <div>
          <p className="mb-4 text-sm text-muted">
            Energy curve showing how your tracks flow from low to high energy.
          </p>
          <div className="rounded-lg border border-border bg-surface p-4">
            <EnergyJourneyView tracks={journeyTracks} />
          </div>
        </div>
      )}
    </div>
  );
}
