"use client";

import { useEffect, useState } from "react";
import { getResult, reportUrl, videoUrl } from "@/lib/api";

interface Props {
  jobId: string;
  onReset: () => void;
}

export default function ResultsDashboard({ jobId, onReset }: Props) {
  const [result, setResult] = useState<{
    total_vehicles: number;
    vehicle_breakdown: Record<string, number>;
    processing_duration_sec: number;
    job_id: string;
  } | null>(null);

  useEffect(() => {
    getResult(jobId).then(setResult).catch(() => {});
  }, [jobId]);

  if (!result) {
    return (
      <div className="flex flex-col items-center gap-4 w-full max-w-2xl">
        <div className="animate-pulse flex flex-col gap-4 w-full">
          <div className="h-8 bg-[#1a1d2e] rounded w-48" />
          <div className="h-32 bg-[#1a1d2e] rounded" />
          <div className="h-24 bg-[#1a1d2e] rounded" />
        </div>
      </div>
    );
  }

  const breakdown = result.vehicle_breakdown;
  const entries = Object.entries(breakdown).filter(([_, v]) => v > 0);

  const colorMap: Record<string, string> = {
    car: "bg-blue-500",
    truck: "bg-red-500",
    bus: "bg-yellow-500",
    motorcycle: "bg-green-500",
  };

  return (
    <div className="flex flex-col items-center gap-6 w-full max-w-4xl">
      <h2 className="text-2xl font-semibold">Analysis Complete</h2>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4 w-full">
        <div className="bg-[#1a1d2e] rounded-xl p-5 text-center">
          <p className="text-gray-400 text-sm">Total Vehicles</p>
          <p className="text-4xl font-bold mt-1">{result.total_vehicles}</p>
        </div>
        <div className="bg-[#1a1d2e] rounded-xl p-5 text-center">
          <p className="text-gray-400 text-sm">Processing Time</p>
          <p className="text-4xl font-bold mt-1">
            {result.processing_duration_sec}s
          </p>
        </div>
      </div>

      {/* Breakdown */}
      {entries.length > 0 && (
        <div className="bg-[#1a1d2e] rounded-xl p-5 w-full">
          <h3 className="text-lg font-medium mb-4">Vehicle Breakdown</h3>
          <div className="flex flex-col gap-3">
            {entries.map(([cls, count]) => {
              const pct = result.total_vehicles
                ? ((count / result.total_vehicles) * 100).toFixed(1)
                : "0";
              return (
                <div key={cls} className="flex items-center gap-3">
                  <div
                    className={`w-3 h-3 rounded-full ${colorMap[cls] || "bg-gray-500"}`}
                  />
                  <span className="w-24 capitalize text-sm">{cls}</span>
                  <div className="flex-1 bg-[#0f1117] rounded-full h-2.5">
                    <div
                      className={`h-full rounded-full ${colorMap[cls] || "bg-gray-500"}`}
                      style={{
                        width: `${result.total_vehicles ? (count / result.total_vehicles) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <span className="text-sm text-gray-400 w-16 text-right">
                    {count} ({pct}%)
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Annotated video player */}
      <div className="w-full bg-[#1a1d2e] rounded-xl p-5">
        <h3 className="text-lg font-medium mb-4">Annotated Video</h3>
        <video
          src={videoUrl(jobId)}
          controls
          playsInline
          className="w-full rounded-lg bg-black"
        >
          Your browser does not support video playback.
        </video>
      </div>

      {/* Downloads */}
      <div className="flex gap-4">
        <a
          href={reportUrl(jobId)}
          download
          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors"
        >
          Download Report
        </a>
        <a
          href={videoUrl(jobId)}
          download
          className="px-5 py-2.5 bg-[#1a1d2e] hover:bg-[#2a2d3e] border border-gray-600 rounded-lg text-sm font-medium transition-colors"
        >
          Download Video
        </a>
      </div>

      <button
        onClick={onReset}
        className="text-gray-400 hover:text-white text-sm transition-colors"
      >
        Analyze another video
      </button>
    </div>
  );
}
