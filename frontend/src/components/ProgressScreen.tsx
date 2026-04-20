"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  jobId: string;
  onDone: (jobId: string) => void;
  onError: (msg: string) => void;
  onCancel: () => void;
}

interface Progress {
  progress_pct: number;
  processed_frames: number;
  total_frames: number;
  status: string;
}

export default function ProgressScreen({ jobId, onDone, onError, onCancel }: Props) {
  const [progress, setProgress] = useState<Progress>({
    progress_pct: 0,
    processed_frames: 0,
    total_frames: 0,
    status: "processing",
  });
  const [wsStatus, setWsStatus] = useState<"connected" | "reconnecting" | "lost">("connected");
  const retries = useRef(0);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;

    function connect() {
      if (closed) return;

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      ws = new WebSocket(`${protocol}//${window.location.host}/ws/progress/${jobId}`);

      ws.onopen = () => {
        retries.current = 0;
        setWsStatus("connected");
      };

      ws.onmessage = (e) => {
        const data: Progress = JSON.parse(e.data);

        if (data.status === "error") {
          onError("Processing failed. Please try again.");
          ws?.close();
          return;
        }

        setProgress(data);

        if (data.status === "done") {
          onDone(jobId);
          ws?.close();
        }
      };

      ws.onclose = () => {
        if (closed) return;
        if (retries.current < 3) {
          retries.current++;
          setWsStatus("reconnecting");
          setTimeout(connect, 3000);
        } else {
          setWsStatus("lost");
        }
      };

      ws.onerror = () => ws?.close();
    }

    connect();
    return () => {
      closed = true;
      ws?.close();
    };
  }, [jobId, onDone, onError]);

  const pct = Math.round(progress.progress_pct);

  return (
    <div className="flex flex-col items-center gap-8 w-full max-w-xl">
      {/* Spinner + title */}
      <div className="flex flex-col items-center gap-3">
        <div className="relative w-16 h-16">
          <div className="absolute inset-0 rounded-full border-4 border-[#1a1d2e]" />
          <div
            className="absolute inset-0 rounded-full border-4 border-transparent border-t-blue-500 animate-spin"
          />
          <div className="absolute inset-0 flex items-center justify-center text-sm font-bold text-blue-400">
            {pct}%
          </div>
        </div>
        <h2 className="text-2xl font-semibold">Analyzing Video</h2>
        <p className="text-gray-500 text-sm">
          Detecting and tracking vehicles with AI...
        </p>
      </div>

      {/* Progress bar */}
      <div className="w-full">
        <div className="w-full bg-[#1a1d2e] rounded-full h-3 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-blue-600 to-blue-400 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="flex justify-between mt-2 text-xs text-gray-500">
          <span>{pct}% complete</span>
          <span>
            {progress.processed_frames.toLocaleString()} / {progress.total_frames.toLocaleString()} frames
          </span>
        </div>
      </div>

      {/* Connection status */}
      {wsStatus === "reconnecting" && (
        <p className="text-yellow-400 text-sm bg-yellow-400/10 px-4 py-2 rounded-lg">
          Connection lost. Reconnecting...
        </p>
      )}
      {wsStatus === "lost" && (
        <p className="text-red-400 text-sm bg-red-400/10 px-4 py-2 rounded-lg">
          Could not reconnect. Please refresh.
        </p>
      )}

      {/* Cancel button */}
      <button
        onClick={onCancel}
        className="px-6 py-2.5 border border-gray-600 hover:border-red-500 hover:text-red-400 rounded-lg text-sm font-medium text-gray-400 transition-colors"
      >
        Stop Analysis
      </button>
    </div>
  );
}
