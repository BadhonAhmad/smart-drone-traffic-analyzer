"use client";

import { useCallback, useState } from "react";

const MAX_SIZE = 500 * 1024 * 1024; // 500 MB

interface Props {
  onFile: (file: File) => void;
}

export default function UploadZone({ onFile }: Props) {
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validate = (file: File): string | null => {
    if (!file.name.toLowerCase().endsWith(".mp4"))
      return "Only .mp4 files are supported.";
    if (file.size > MAX_SIZE) return "File exceeds 500 MB limit.";
    return null;
  };

  const handle = (file: File) => {
    const err = validate(file);
    if (err) {
      setError(err);
      return;
    }
    setError(null);
    onFile(file);
  };

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDrag(false);
      const file = e.dataTransfer.files[0];
      if (file) handle(file);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handle(file);
  };

  return (
    <div className="flex flex-col items-center gap-8">
      <h1 className="text-3xl font-bold tracking-tight">
        Smart Drone Traffic Analyzer
      </h1>
      <p className="text-gray-400 text-center max-w-lg">
        Upload a drone surveillance video to detect, track, and count vehicles
        using AI-powered analysis.
      </p>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        className={`relative flex flex-col items-center justify-center w-full max-w-xl h-64 border-2 border-dashed rounded-2xl transition-colors cursor-pointer ${
          drag
            ? "border-blue-500 bg-blue-500/10"
            : "border-gray-600 hover:border-gray-400 bg-[#1a1d2e]"
        }`}
        onClick={() => document.getElementById("file-input")?.click()}
      >
        <svg
          className="w-12 h-12 mb-3 text-gray-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>
        <p className="text-gray-400 text-sm">
          Drag & drop an <span className="text-white font-medium">.mp4</span>{" "}
          file or click to browse
        </p>
        <p className="text-gray-500 text-xs mt-1">Max 500 MB</p>

        <input
          id="file-input"
          type="file"
          accept=".mp4,video/mp4"
          className="hidden"
          onChange={onChange}
        />
      </div>

      {error && (
        <p className="text-red-400 text-sm bg-red-400/10 px-4 py-2 rounded-lg">
          {error}
        </p>
      )}
    </div>
  );
}
