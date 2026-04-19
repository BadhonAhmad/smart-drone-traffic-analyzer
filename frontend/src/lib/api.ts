import axios from "axios";

const api = axios.create({ baseURL: "/api" });

export async function uploadVideo(file: File): Promise<{ job_id: string }> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<{ job_id: string }>("/upload", form);
  return data;
}

export async function getJobStatus(jobId: string) {
  const { data } = await api.get(`/job/${jobId}`);
  return data as {
    status: string;
    progress_pct: number;
    total_frames: number;
    processed_frames: number;
  };
}

export async function getResult(jobId: string) {
  const { data } = await api.get(`/result/${jobId}`);
  return data as {
    total_vehicles: number;
    vehicle_breakdown: Record<string, number>;
    processing_duration_sec: number;
    job_id: string;
  };
}

export function reportUrl(jobId: string) {
  return `/api/report/${jobId}`;
}

export function videoUrl(jobId: string) {
  return `/api/video/${jobId}`;
}
