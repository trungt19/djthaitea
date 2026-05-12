import playlistsData from "@/data/playlists.json";
import { Playlist } from "@/types";

export function getAllPlaylists(): Playlist[] {
  return playlistsData as Playlist[];
}

export function getPlaylistBySlug(slug: string): Playlist | undefined {
  return getAllPlaylists().find((p) => p.slug === slug);
}
