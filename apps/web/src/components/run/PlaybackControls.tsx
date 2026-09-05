"use client";

import { Pause, Play, RotateCcw, SkipBack, SkipForward } from "lucide-react";
import { usePlayback } from "@/lib/demo/playback";
import { cn } from "@/lib/cn";

/**
 * Transport controls for the demo replay.
 *
 * Renders nothing in live mode, where the run advances because the buyer agent
 * is actually working rather than because a timer said so.
 */
export function PlaybackControls({ note }: { note?: string }) {
  const playback = usePlayback();
  if (!playback) return null;

  const { step, stepCount, isPlaying, isFinished, toggle, next, previous, restart } = playback;
  const progress = stepCount === 0 ? 0 : (step / stepCount) * 100;

  return (
    <div className="rounded-panel border border-border bg-surface px-4 py-3">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1">
          <ControlButton label="Previous step" onClick={previous} disabled={step === 0}>
            <SkipBack className="size-3.5" aria-hidden />
          </ControlButton>

          <button
            type="button"
            onClick={isFinished ? restart : toggle}
            aria-label={isFinished ? "Replay" : isPlaying ? "Pause" : "Play"}
            className={cn(
              "grid size-9 place-items-center rounded-full transition-all",
              "bg-rescue text-canvas hover:brightness-110",
            )}
          >
            {isFinished ? (
              <RotateCcw className="size-4" aria-hidden />
            ) : isPlaying ? (
              <Pause className="size-4" aria-hidden />
            ) : (
              <Play className="size-4 translate-x-px" aria-hidden />
            )}
          </button>

          <ControlButton label="Next step" onClick={next} disabled={isFinished}>
            <SkipForward className="size-3.5" aria-hidden />
          </ControlButton>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-3">
            <p className="truncate text-sm text-ink-muted">{note || "Ready."}</p>
            <span className="shrink-0 font-mono text-xs tabular-nums text-ink-subtle">
              {step}/{stepCount}
            </span>
          </div>
          <div
            className="mt-2 h-1 overflow-hidden rounded-full bg-surface-raised"
            role="progressbar"
            aria-valuenow={step}
            aria-valuemin={0}
            aria-valuemax={stepCount}
            aria-label="Demo progress"
          >
            <div
              className="h-full rounded-full bg-rescue transition-[width] duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function ControlButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className={cn(
        "grid size-8 place-items-center rounded-lg text-ink-muted transition-colors",
        "hover:bg-surface-hover hover:text-ink",
        "disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent",
      )}
    >
      {children}
    </button>
  );
}
