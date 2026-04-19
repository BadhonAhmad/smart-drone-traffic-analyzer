"use client";

import { useCallback, useState } from "react";
import UploadZone from "@/components/UploadZone";
import ProgressScreen from "@/components/ProgressScreen";
import ResultsDashboard from "@/components/ResultsDashboard";
import ErrorCard from "@/components/ErrorCard";
import { uploadVideo } from "@/lib/api";

type Screen = "upload" | "processing" | "done" | "error";

export default function Home() {
  const [screen, setScreen] = useState<Screen>("upload");
  const [jobId, setJobId] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const handleFile = useCallback(async (file: File) => {
    try {
      setScreen("processing");
      const { job_id } = await uploadVideo(file);
      setJobId(job_id);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Upload failed. Please try again.";
      setErrorMsg(msg);
      setScreen("error");
    }
  }, []);

  const handleDone = useCallback(() => setScreen("done"), []);
  const handleError = useCallback((msg: string) => {
    setErrorMsg(msg);
    setScreen("error");
  }, []);

  const reset = useCallback(() => {
    setScreen("upload");
    setJobId("");
    setErrorMsg("");
  }, []);

  return (
    <main className="flex items-center justify-center min-h-screen px-4">
      {screen === "upload" && <UploadZone onFile={handleFile} />}
      {screen === "processing" && jobId && (
        <ProgressScreen jobId={jobId} onDone={handleDone} onError={handleError} />
      )}
      {screen === "done" && jobId && (
        <ResultsDashboard jobId={jobId} onReset={reset} />
      )}
      {screen === "error" && <ErrorCard message={errorMsg} onReset={reset} />}
    </main>
  );
}
