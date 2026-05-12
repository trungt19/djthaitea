export interface Track {
  id: string;
  title: string;
  audioFile: string;
  bpm: number;
  key: string;
  keyMode: "major" | "minor";
  camelotCode: string;
  genres: string[];
  moods: string[];
  energy: number;
  hasVocals: boolean;
  source: "suno" | "original";
  duration: number;
  dateAdded: string;
}

export interface PlaylistTrack {
  trackId: string;
  transitionNote?: string;
}

export interface Playlist {
  id: string;
  slug: string;
  name: string;
  description: string;
  tracks: PlaylistTrack[];
  createdAt: string;
  updatedAt: string;
}

export type Genre =
  | "tech-house"
  | "dark-trap"
  | "melodic-house"
  | "synthwave"
  | "hip-hop"
  | "ambient"
  | "trap"
  | "edm"
  | "cinematic"
  | "trance"
  | "melodic-trance"
  | "dnb"
  | "atmospheric";

export type Mood =
  | "dark"
  | "aggressive"
  | "euphoric"
  | "dreamy"
  | "moody"
  | "energetic"
  | "reflective"
  | "cinematic"
  | "angelic"
  | "atmospheric";
