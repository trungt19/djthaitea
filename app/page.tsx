import Link from "next/link";
import { getAllTracks } from "@/lib/tracks";
import { getAllPlaylists } from "@/lib/playlists";

export default function HomePage() {
  const tracks = getAllTracks();
  const playlists = getAllPlaylists();

  return (
    <div className="relative">
      {/* Hero */}
      <section className="relative flex min-h-[70vh] flex-col items-center justify-center px-4 text-center">
        {/* Gradient background */}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-neon-cyan/5 via-transparent to-neon-magenta/5" />

        <h1 className="font-[family-name:var(--font-space-grotesk)] text-6xl font-bold tracking-tight sm:text-7xl">
          <span className="text-glow-cyan text-neon-cyan">DJ</span>{" "}
          <span className="text-foreground">THAI TEA</span>
        </h1>
        <p className="mt-4 max-w-lg text-lg text-muted">
          Dark atmospheric EDM. Trap. Hip-hop with rap vocals.
          <br />
          Music that takes you on a journey.
        </p>

        <div className="mt-8 flex gap-4">
          <Link
            href="/tracks"
            className="glow-cyan rounded-lg bg-neon-cyan/10 px-6 py-3 font-semibold text-neon-cyan transition-all hover:bg-neon-cyan/20"
          >
            Explore Tracks
          </Link>
          <Link
            href="/builder"
            className="rounded-lg border border-border px-6 py-3 font-semibold text-foreground transition-all hover:border-neon-magenta hover:text-neon-magenta"
          >
            Build a Set
          </Link>
        </div>

        {/* Stats */}
        <div className="mt-16 flex gap-12 text-center">
          <div>
            <div className="font-[family-name:var(--font-space-grotesk)] text-3xl font-bold text-neon-cyan">
              {tracks.length}
            </div>
            <div className="mt-1 text-sm text-muted">Tracks</div>
          </div>
          <div>
            <div className="font-[family-name:var(--font-space-grotesk)] text-3xl font-bold text-neon-magenta">
              {playlists.length}
            </div>
            <div className="mt-1 text-sm text-muted">DJ Sets</div>
          </div>
          <div>
            <div className="font-[family-name:var(--font-space-grotesk)] text-3xl font-bold text-neon-lime">
              {new Set(tracks.flatMap((t) => t.genres)).size}
            </div>
            <div className="mt-1 text-sm text-muted">Genres</div>
          </div>
        </div>
      </section>

      {/* Featured tracks */}
      <section className="mx-auto max-w-7xl px-4 py-16">
        <h2 className="font-[family-name:var(--font-space-grotesk)] text-2xl font-bold">
          Latest Tracks
        </h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {tracks.slice(0, 4).map((track) => (
            <div
              key={track.id}
              className="rounded-lg border border-border bg-surface p-5 transition-colors hover:bg-surface-light"
            >
              <h3 className="font-[family-name:var(--font-space-grotesk)] font-semibold">
                {track.title}
              </h3>
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted">
                <span>{track.bpm} BPM</span>
                <span>
                  {track.key}
                  {track.keyMode === "minor" ? "m" : ""}
                </span>
                <span>Energy: {track.energy}/10</span>
                {track.hasVocals && (
                  <span className="text-neon-magenta">Vocals</span>
                )}
              </div>
              <div className="mt-3 flex gap-1.5">
                {track.genres.map((g) => (
                  <span
                    key={g}
                    className="rounded-full border border-border px-2 py-0.5 text-xs text-muted"
                  >
                    {g}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
