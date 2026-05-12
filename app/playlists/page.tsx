import Link from "next/link";
import { getAllPlaylists } from "@/lib/playlists";
import { getTrackById } from "@/lib/tracks";

export default function PlaylistsPage() {
  const playlists = getAllPlaylists();

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-8">
        <h1 className="font-[family-name:var(--font-space-grotesk)] text-3xl font-bold tracking-tight text-glow-cyan text-neon-cyan">
          DJ Sets
        </h1>
        <p className="mt-2 text-muted">Curated track orderings for live sets</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {playlists.map((playlist) => {
          const trackCount = playlist.tracks.length;
          const totalDuration = playlist.tracks.reduce((acc, pt) => {
            const track = getTrackById(pt.trackId);
            return acc + (track?.duration || 0);
          }, 0);

          return (
            <Link
              key={playlist.id}
              href={`/playlists/${playlist.slug}`}
              className="group rounded-lg border border-border bg-surface p-5 transition-all hover:border-neon-cyan/30 hover:bg-surface-light"
            >
              <h3 className="font-[family-name:var(--font-space-grotesk)] text-lg font-semibold group-hover:text-neon-cyan">
                {playlist.name}
              </h3>
              <p className="mt-1 text-sm text-muted">{playlist.description}</p>
              <div className="mt-3 flex gap-4 text-xs text-muted">
                <span>{trackCount} tracks</span>
                <span>
                  {Math.floor(totalDuration / 60)} min
                </span>
              </div>
            </Link>
          );
        })}
      </div>

      {playlists.length === 0 && (
        <div className="py-20 text-center text-muted">
          <p>No sets created yet</p>
          <Link href="/builder" className="mt-2 text-neon-cyan hover:underline">
            Build your first set
          </Link>
        </div>
      )}
    </div>
  );
}
