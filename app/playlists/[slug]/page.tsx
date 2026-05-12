import { notFound } from "next/navigation";
import { getAllPlaylists, getPlaylistBySlug } from "@/lib/playlists";
import { getTrackById } from "@/lib/tracks";
import { formatDuration, getEnergyColor } from "@/lib/utils";
import { getCompatibility, getCompatibilityColor } from "@/lib/camelot";

export function generateStaticParams() {
  return getAllPlaylists().map((p) => ({ slug: p.slug }));
}

export default async function PlaylistPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const playlist = getPlaylistBySlug(slug);
  if (!playlist) notFound();

  const tracks = playlist.tracks
    .map((pt) => ({ ...pt, track: getTrackById(pt.trackId) }))
    .filter((pt) => pt.track != null);

  const totalDuration = tracks.reduce(
    (acc, pt) => acc + (pt.track?.duration || 0),
    0
  );

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-8">
        <h1 className="font-[family-name:var(--font-space-grotesk)] text-3xl font-bold">
          {playlist.name}
        </h1>
        <p className="mt-2 text-muted">{playlist.description}</p>
        <div className="mt-3 flex gap-4 text-sm text-muted">
          <span>{tracks.length} tracks</span>
          <span>{Math.floor(totalDuration / 60)} min</span>
        </div>
      </div>

      <div className="flex flex-col">
        {tracks.map((pt, index) => {
          const track = pt.track!;
          const prevTrack = index > 0 ? tracks[index - 1].track! : null;

          return (
            <div key={track.id}>
              {/* Key compatibility indicator between tracks */}
              {prevTrack && (
                <div className="mx-6 flex items-center gap-3 py-1">
                  <div className="flex flex-col items-center">
                    <div className="h-3 w-px bg-border" />
                    <div
                      className="h-2 w-2 rounded-full"
                      style={{
                        backgroundColor: getCompatibilityColor(
                          getCompatibility(
                            prevTrack.camelotCode,
                            track.camelotCode
                          )
                        ),
                      }}
                    />
                    <div className="h-3 w-px bg-border" />
                  </div>
                  {pt.transitionNote && (
                    <span className="text-xs italic text-muted">
                      {pt.transitionNote}
                    </span>
                  )}
                </div>
              )}

              {/* Track row */}
              <div className="flex items-center gap-4 rounded-lg border border-border bg-surface p-4">
                <span className="w-6 text-center text-sm text-muted">
                  {index + 1}
                </span>

                <div className="min-w-0 flex-1">
                  <h3 className="font-[family-name:var(--font-space-grotesk)] font-semibold">
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

                {/* Energy */}
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
            </div>
          );
        })}
      </div>
    </div>
  );
}
