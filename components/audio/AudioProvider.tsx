"use client";

import {
  createContext,
  useContext,
  useState,
  useRef,
  useCallback,
  ReactNode,
} from "react";
import { Track } from "@/types";

interface AudioState {
  currentTrack: Track | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
}

interface AudioContextType extends AudioState {
  play: (track: Track) => void;
  pause: () => void;
  resume: () => void;
  toggle: (track: Track) => void;
  seek: (time: number) => void;
  audioRef: React.RefObject<HTMLAudioElement | null>;
}

const AudioContext = createContext<AudioContextType | null>(null);

export function useAudio() {
  const ctx = useContext(AudioContext);
  if (!ctx) throw new Error("useAudio must be used within AudioProvider");
  return ctx;
}

export function AudioProvider({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [state, setState] = useState<AudioState>({
    currentTrack: null,
    isPlaying: false,
    currentTime: 0,
    duration: 0,
  });

  const play = useCallback((track: Track) => {
    const audio = audioRef.current;
    if (!audio) return;

    audio.src = track.audioFile;
    audio.play().catch(() => {});
    setState((s) => ({
      ...s,
      currentTrack: track,
      isPlaying: true,
      currentTime: 0,
    }));
  }, []);

  const pause = useCallback(() => {
    audioRef.current?.pause();
    setState((s) => ({ ...s, isPlaying: false }));
  }, []);

  const resume = useCallback(() => {
    audioRef.current?.play().catch(() => {});
    setState((s) => ({ ...s, isPlaying: true }));
  }, []);

  const toggle = useCallback(
    (track: Track) => {
      if (state.currentTrack?.id === track.id) {
        if (state.isPlaying) pause();
        else resume();
      } else {
        play(track);
      }
    },
    [state.currentTrack, state.isPlaying, play, pause, resume]
  );

  const seek = useCallback((time: number) => {
    const audio = audioRef.current;
    if (audio) {
      audio.currentTime = time;
      setState((s) => ({ ...s, currentTime: time }));
    }
  }, []);

  return (
    <AudioContext value={{ ...state, play, pause, resume, toggle, seek, audioRef }}>
      {children}
      <audio
        ref={audioRef}
        onTimeUpdate={() => {
          const t = audioRef.current;
          if (t) setState((s) => ({ ...s, currentTime: t.currentTime }));
        }}
        onLoadedMetadata={() => {
          const t = audioRef.current;
          if (t) setState((s) => ({ ...s, duration: t.duration }));
        }}
        onEnded={() => {
          setState((s) => ({ ...s, isPlaying: false, currentTime: 0 }));
        }}
      />
    </AudioContext>
  );
}
