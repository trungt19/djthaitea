"use client";

import { useState, useCallback } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Track } from "@/types";
import { getEnergyColor, formatDuration } from "@/lib/utils";
import { TransitionNotes } from "./TransitionNotes";
import { EnergyArcChart } from "./EnergyArcChart";

interface SetTrack {
  track: Track;
  transitionNote: string;
}

interface PlaylistBuilderProps {
  allTracks: Track[];
  initialTracks?: SetTrack[];
}

function SortableTrackItem({
  item,
  onRemove,
}: {
  item: SetTrack;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: item.track.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-3 rounded-lg border border-border bg-surface p-3"
    >
      {/* Drag handle */}
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab touch-none text-muted hover:text-foreground"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
          <circle cx="5" cy="4" r="1.5" />
          <circle cx="11" cy="4" r="1.5" />
          <circle cx="5" cy="8" r="1.5" />
          <circle cx="11" cy="8" r="1.5" />
          <circle cx="5" cy="12" r="1.5" />
          <circle cx="11" cy="12" r="1.5" />
        </svg>
      </button>

      {/* Track info */}
      <div className="flex-1 min-w-0">
        <div className="truncate font-[family-name:var(--font-space-grotesk)] text-sm font-semibold">
          {item.track.title}
        </div>
        <div className="text-xs text-muted">
          {item.track.bpm} BPM · {item.track.camelotCode} · {formatDuration(item.track.duration)}
        </div>
      </div>

      {/* Energy indicator */}
      <div className="flex gap-0.5">
        {Array.from({ length: 10 }, (_, i) => (
          <div
            key={i}
            className="h-3 w-0.5 rounded-full"
            style={{
              backgroundColor:
                i < item.track.energy
                  ? getEnergyColor(item.track.energy)
                  : "rgba(255,255,255,0.05)",
            }}
          />
        ))}
      </div>

      {/* Remove button */}
      <button
        onClick={onRemove}
        className="text-muted hover:text-red-400 transition-colors"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 3l8 8M11 3l-8 8" />
        </svg>
      </button>
    </div>
  );
}

export function PlaylistBuilder({ allTracks, initialTracks = [] }: PlaylistBuilderProps) {
  const [setTracks, setSetTracks] = useState<SetTrack[]>(initialTracks);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setSetTracks((items) => {
        const oldIndex = items.findIndex((i) => i.track.id === active.id);
        const newIndex = items.findIndex((i) => i.track.id === over.id);
        return arrayMove(items, oldIndex, newIndex);
      });
    }
  }, []);

  const addTrack = useCallback((track: Track) => {
    setSetTracks((prev) => {
      if (prev.some((t) => t.track.id === track.id)) return prev;
      return [...prev, { track, transitionNote: "" }];
    });
  }, []);

  const removeTrack = useCallback((trackId: string) => {
    setSetTracks((prev) => prev.filter((t) => t.track.id !== trackId));
  }, []);

  const updateNote = useCallback((index: number, note: string) => {
    setSetTracks((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], transitionNote: note };
      return next;
    });
  }, []);

  const availableTracks = allTracks.filter(
    (t) => !setTracks.some((st) => st.track.id === t.id)
  );

  return (
    <div className="grid gap-8 lg:grid-cols-3">
      {/* Available tracks (sidebar) */}
      <div className="lg:col-span-1">
        <h3 className="font-[family-name:var(--font-space-grotesk)] font-semibold mb-3">
          Available Tracks
        </h3>
        <div className="flex flex-col gap-2">
          {availableTracks.map((track) => (
            <button
              key={track.id}
              onClick={() => addTrack(track)}
              className="flex items-center gap-3 rounded-lg border border-border bg-surface p-3 text-left transition-colors hover:bg-surface-light"
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 14 14"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="shrink-0 text-neon-lime"
              >
                <path d="M7 2v10M2 7h10" />
              </svg>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold">{track.title}</div>
                <div className="text-xs text-muted">
                  {track.bpm} BPM · {track.camelotCode} · E:{track.energy}
                </div>
              </div>
            </button>
          ))}
          {availableTracks.length === 0 && (
            <p className="py-4 text-center text-xs text-muted">
              All tracks added to set
            </p>
          )}
        </div>
      </div>

      {/* Set builder (main area) */}
      <div className="lg:col-span-2">
        {/* Energy arc */}
        <div className="mb-6 rounded-lg border border-border bg-surface p-4">
          <h3 className="font-[family-name:var(--font-space-grotesk)] text-sm font-semibold mb-2">
            Energy Arc
          </h3>
          <EnergyArcChart tracks={setTracks.map((s) => s.track)} />
        </div>

        {/* Track list with drag-and-drop */}
        <h3 className="font-[family-name:var(--font-space-grotesk)] font-semibold mb-3">
          Set Order ({setTracks.length} tracks)
        </h3>

        {setTracks.length === 0 ? (
          <div className="flex h-40 items-center justify-center rounded-lg border-2 border-dashed border-border text-sm text-muted">
            Add tracks from the left to build your set
          </div>
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={setTracks.map((s) => s.track.id)}
              strategy={verticalListSortingStrategy}
            >
              <div className="flex flex-col">
                {setTracks.map((item, index) => (
                  <div key={item.track.id}>
                    <SortableTrackItem
                      item={item}
                      onRemove={() => removeTrack(item.track.id)}
                    />
                    {index < setTracks.length - 1 && (
                      <TransitionNotes
                        fromTrack={item.track}
                        toTrack={setTracks[index + 1].track}
                        note={item.transitionNote}
                        onNoteChange={(note) => updateNote(index, note)}
                      />
                    )}
                  </div>
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>
    </div>
  );
}
