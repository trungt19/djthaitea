"use client";

import { PlaylistBuilder } from "@/components/builder/PlaylistBuilder";
import { getAllTracks } from "@/lib/tracks";

export default function BuilderPage() {
  const tracks = getAllTracks();

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-8">
        <h1 className="font-[family-name:var(--font-space-grotesk)] text-3xl font-bold tracking-tight text-glow-cyan text-neon-cyan">
          Set Builder
        </h1>
        <p className="mt-2 text-muted">
          Drag and drop tracks to craft your DJ set. Watch the energy arc update
          in real-time.
        </p>
      </div>

      <PlaylistBuilder allTracks={tracks} />
    </div>
  );
}
