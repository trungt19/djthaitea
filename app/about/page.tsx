export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="font-[family-name:var(--font-space-grotesk)] text-4xl font-bold tracking-tight">
        About <span className="text-neon-cyan text-glow-cyan">DJ Thai Tea</span>
      </h1>

      <div className="mt-8 space-y-6 text-muted leading-relaxed">
        <p>
          DJ Thai Tea blends dark atmospheric EDM with trap, hip-hop, and
          cinematic soundscapes. The sound sits at the intersection of dark
          synths, heavy bass, and chopped vocal textures — music that&apos;s
          danceable but takes listeners on a journey from intimate whispers to
          cathedral-shaking drops.
        </p>

        <p>
          Every set is a story: starting from ambient grooves, building through
          melodic layers, peaking with aggressive trap energy, then guiding
          listeners back down. The Camelot wheel and energy arc tools on this
          site are how each set gets crafted — harmonic mixing meets intentional
          energy design.
        </p>

        <p>
          Tracks feature original rap and sung vocals over AI-assisted
          production via Suno, post-processed and mixed to create a signature
          sound that blends human creativity with modern tools.
        </p>
      </div>

      {/* Sound DNA */}
      <div className="mt-12">
        <h2 className="font-[family-name:var(--font-space-grotesk)] text-xl font-bold mb-6">
          Sound DNA
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {[
            {
              label: "Dark Synths",
              ref: "Moody pads, neon noir atmospheres, late-night energy",
              color: "#00f0ff",
            },
            {
              label: "Chopped Vocals",
              ref: "Stuttered angel voices, glitched transmissions, whispered textures",
              color: "#ff00aa",
            },
            {
              label: "Tech House",
              ref: "Driving grooves, heavy basslines, peak-time pressure",
              color: "#39ff14",
            },
            {
              label: "Cinematic",
              ref: "Film score breakdowns, cathedral reverb, emotional arcs",
              color: "#a855f7",
            },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-lg border border-border bg-surface p-4"
            >
              <div
                className="text-sm font-semibold"
                style={{ color: item.color }}
              >
                {item.label}
              </div>
              <div className="mt-1 text-xs text-muted">{item.ref}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Links */}
      <div className="mt-12">
        <h2 className="font-[family-name:var(--font-space-grotesk)] text-xl font-bold mb-4">
          Links
        </h2>
        <div className="flex flex-wrap gap-3">
          {[
            { label: "Spotify", href: "#" },
            { label: "SoundCloud", href: "#" },
            { label: "Instagram", href: "#" },
          ].map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="rounded-lg border border-border px-4 py-2 text-sm text-muted transition-colors hover:border-neon-cyan hover:text-neon-cyan"
            >
              {link.label}
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
