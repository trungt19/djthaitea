import tracksData from "@/data/tracks.json";
import { Track } from "@/types";

export function getAllTracks(): Track[] {
  return tracksData as Track[];
}

export function getTrackById(id: string): Track | undefined {
  return getAllTracks().find((t) => t.id === id);
}

export function getTracksByGenre(genre: string): Track[] {
  return getAllTracks().filter((t) => t.genres.includes(genre));
}

export function getTracksByEnergyRange(min: number, max: number): Track[] {
  return getAllTracks().filter((t) => t.energy >= min && t.energy <= max);
}

export function getAllGenres(): string[] {
  const genres = new Set<string>();
  getAllTracks().forEach((t) => t.genres.forEach((g) => genres.add(g)));
  return Array.from(genres).sort();
}

export function getAllMoods(): string[] {
  const moods = new Set<string>();
  getAllTracks().forEach((t) => t.moods.forEach((m) => moods.add(m)));
  return Array.from(moods).sort();
}
