"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  jobId: string;
  onDone: (jobId: string) => void;
  onError: (msg: string) => void;
}

interface Progress {
  progress_pct: number;
  processed_frames: number;
  total_frames: number;
  status: string;
}

export default function ProgressScreen({ jobId, onDone, onError }: Props) {
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
          onError(data.status === "error" ? "Processing failed" : "Unknown error");
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
    <div className="flex flex-col items-center gap-6 w-full max-w-xl">
      <h2 className="text-2xl font-semibold">Processing Video</h2>

      <div className="w-full bg-[#1a1d2e] rounded-full h-4 overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>

      <div className="flex justify-between w-full text-sm text-gray-400">
        <span>{pct}% complete</span>
        <span>
          {progress.processed_frames} / {progress.total_frames} frames
        </span>
      </div>

      {wsStatus === "reconnecting" && (
        <p className="text-yellow-400 text-sm">
          Connection lost. Retrying...
        </p>
      )}
      {wsStatus === "lost" && (
        <p className="text-red-400 text-sm">
          Could not reconnect. Please refresh.
        </p>
      )}
    </div>
  );
}
