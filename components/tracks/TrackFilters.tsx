"use client";

interface TrackFiltersProps {
  genres: string[];
  selectedGenre: string;
  onGenreChange: (genre: string) => void;
  energyRange: [number, number];
  onEnergyChange: (range: [number, number]) => void;
  vocalsOnly: boolean;
  onVocalsChange: (v: boolean) => void;
}

export function TrackFilters({
  genres,
  selectedGenre,
  onGenreChange,
  vocalsOnly,
  onVocalsChange,
}: TrackFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Genre filter */}
      <div className="flex flex-wrap gap-1.5">
        <button
          onClick={() => onGenreChange("")}
          className={`rounded-full px-3 py-1 text-xs transition-colors ${
            selectedGenre === ""
              ? "bg-neon-cyan/20 text-neon-cyan"
              : "border border-border text-muted hover:text-foreground"
          }`}
        >
          All
        </button>
        {genres.map((genre) => (
          <button
            key={genre}
            onClick={() => onGenreChange(genre)}
            className={`rounded-full px-3 py-1 text-xs transition-colors ${
              selectedGenre === genre
                ? "bg-neon-cyan/20 text-neon-cyan"
                : "border border-border text-muted hover:text-foreground"
            }`}
          >
            {genre}
          </button>
        ))}
      </div>

      {/* Vocals toggle */}
      <button
        onClick={() => onVocalsChange(!vocalsOnly)}
        className={`rounded-full px-3 py-1 text-xs transition-colors ${
          vocalsOnly
            ? "bg-neon-magenta/20 text-neon-magenta"
            : "border border-border text-muted hover:text-foreground"
        }`}
      >
        Vocals Only
      </button>
    </div>
  );
}
