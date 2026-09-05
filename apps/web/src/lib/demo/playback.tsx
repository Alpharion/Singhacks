"use client";

/**
 * Demo playback clock.
 *
 * Advances through the demo beats on a timer so the run unfolds on screen
 * instead of appearing finished. Exposes play / pause / step / restart so a
 * presenter can hold on any beat and talk over it.
 *
 * Fixture mode only. In live mode `step` is irrelevant and the run comes from
 * polling the buyer agent.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { DEMO_BEAT_INTERVAL_MS } from "@/lib/api/config";
import { DEMO_STEP_COUNT } from "./runProjection";

export interface PlaybackState {
  /** 0 = nothing has happened yet; DEMO_STEP_COUNT = finished. */
  step: number;
  stepCount: number;
  isPlaying: boolean;
  isFinished: boolean;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  next: () => void;
  previous: () => void;
  restart: () => void;
  goTo: (step: number) => void;
}

const PlaybackContext = createContext<PlaybackState | null>(null);

export function DemoPlaybackProvider({
  children,
  autoPlay = true,
}: {
  children: ReactNode;
  autoPlay?: boolean;
}) {
  const [step, setStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(autoPlay);
  const isFinished = step >= DEMO_STEP_COUNT;

  // Keep the interval stable across re-renders; only the tick reads state.
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!isPlaying) return;

    timer.current = setInterval(() => {
      setStep((current) => {
        if (current >= DEMO_STEP_COUNT) {
          setIsPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, DEMO_BEAT_INTERVAL_MS);

    return () => {
      if (timer.current) clearInterval(timer.current);
      timer.current = null;
    };
  }, [isPlaying]);

  const goTo = useCallback((target: number) => {
    setStep(Math.max(0, Math.min(target, DEMO_STEP_COUNT)));
  }, []);

  const value = useMemo<PlaybackState>(
    () => ({
      step,
      stepCount: DEMO_STEP_COUNT,
      isPlaying,
      isFinished,
      play: () => {
        // Replaying from the end should start over rather than sit still.
        setStep((current) => (current >= DEMO_STEP_COUNT ? 0 : current));
        setIsPlaying(true);
      },
      pause: () => setIsPlaying(false),
      toggle: () => setIsPlaying((playing) => !playing),
      next: () => {
        setIsPlaying(false);
        goTo(step + 1);
      },
      previous: () => {
        setIsPlaying(false);
        goTo(step - 1);
      },
      restart: () => {
        setStep(0);
        setIsPlaying(true);
      },
      goTo: (target: number) => {
        setIsPlaying(false);
        goTo(target);
      },
    }),
    [step, isPlaying, isFinished, goTo],
  );

  return <PlaybackContext.Provider value={value}>{children}</PlaybackContext.Provider>;
}

/** Playback controls, or null when the app is running against the live API. */
export function usePlayback(): PlaybackState | null {
  return useContext(PlaybackContext);
}
