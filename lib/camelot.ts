// Camelot Wheel mapping for harmonic mixing
// The Camelot system maps musical keys to a numbered wheel (1-12, A/B)
// A = minor, B = major
// Compatible keys: same number, +1, -1, or same number opposite letter

export const CAMELOT_WHEEL: Record<string, { key: string; mode: string }> = {
  "1A": { key: "Ab", mode: "minor" },
  "1B": { key: "B", mode: "major" },
  "2A": { key: "Eb", mode: "minor" },
  "2B": { key: "F#", mode: "major" },
  "3A": { key: "Bb", mode: "minor" },
  "3B": { key: "Db", mode: "major" },
  "4A": { key: "F", mode: "minor" },
  "4B": { key: "Ab", mode: "major" },
  "5A": { key: "C", mode: "minor" },
  "5B": { key: "Eb", mode: "major" },
  "6A": { key: "G", mode: "minor" },
  "6B": { key: "Bb", mode: "major" },
  "7A": { key: "D", mode: "minor" },
  "7B": { key: "F", mode: "major" },
  "8A": { key: "A", mode: "minor" },
  "8B": { key: "C", mode: "major" },
  "9A": { key: "E", mode: "minor" },
  "9B": { key: "G", mode: "major" },
  "10A": { key: "B", mode: "minor" },
  "10B": { key: "D", mode: "major" },
  "11A": { key: "F#", mode: "minor" },
  "11B": { key: "A", mode: "major" },
  "12A": { key: "Db", mode: "minor" },
  "12B": { key: "E", mode: "major" },
};

export type CompatibilityLevel = "perfect" | "compatible" | "clash";

export function getCompatibility(
  code1: string,
  code2: string
): CompatibilityLevel {
  const num1 = parseInt(code1);
  const num2 = parseInt(code2);
  const letter1 = code1.slice(-1);
  const letter2 = code2.slice(-1);

  // Same key = perfect
  if (code1 === code2) return "perfect";

  // Same number, different letter (relative major/minor) = perfect
  if (num1 === num2 && letter1 !== letter2) return "perfect";

  // Adjacent numbers, same letter = compatible
  const diff = Math.abs(num1 - num2);
  if ((diff === 1 || diff === 11) && letter1 === letter2) return "compatible";

  return "clash";
}

export function getCompatibilityColor(level: CompatibilityLevel): string {
  switch (level) {
    case "perfect":
      return "#39ff14"; // lime green
    case "compatible":
      return "#facc15"; // yellow
    case "clash":
      return "#ef4444"; // red
  }
}

export function getCompatibleKeys(camelotCode: string): string[] {
  const num = parseInt(camelotCode);
  const letter = camelotCode.slice(-1);
  const oppositeLetter = letter === "A" ? "B" : "A";

  const prev = ((num - 2 + 12) % 12) + 1;
  const next = (num % 12) + 1;

  return [
    `${prev}${letter}`,
    camelotCode,
    `${next}${letter}`,
    `${num}${oppositeLetter}`,
  ];
}

export const ALL_CAMELOT_CODES = Object.keys(CAMELOT_WHEEL);
