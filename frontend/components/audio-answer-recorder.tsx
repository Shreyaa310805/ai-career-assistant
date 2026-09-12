"use client";

import { useEffect, useRef, useState } from "react";
import { Alert, Button } from "@/components/ui";

export function AudioAnswerRecorder({ disabled, onSubmit, onBusy }: {
  disabled: boolean;
  onSubmit: (blob: Blob, duration: number) => Promise<void>;
  onBusy: (busy: boolean) => void;
}) {
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const mounted = useRef(true);
  const starting = useRef(false);
  const started = useRef(0);
  const [recording, setRecording] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [clip, setClip] = useState<Blob | null>(null);
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (recorder.current?.state === "recording") recorder.current.stop();
      stream.current?.getTracks().forEach(track => track.stop());
    };
  }, []);
  useEffect(() => {
    if (!clip) { setUrl(""); return; }
    const next = URL.createObjectURL(clip);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [clip]);
  useEffect(() => {
    if (!recording) return;
    const timer = window.setInterval(() => {
      setSeconds(Math.min(600, (Date.now() - started.current) / 1000));
      if (Date.now() - started.current >= 600000 && recorder.current?.state === "recording") recorder.current.stop();
    }, 250);
    return () => window.clearInterval(timer);
  }, [recording]);

  async function start() {
    if (starting.current || recording || disabled) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Audio recording is unavailable. Use a supported browser on HTTPS or localhost."); return;
    }
    const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"]
      .find(type => MediaRecorder.isTypeSupported(type));
    if (!mimeType) { setError("This browser has no supported audio recording format."); return; }
    starting.current = true;
    setRequesting(true); onBusy(true); setError(""); setClip(null);
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mounted.current) { media.getTracks().forEach(track => track.stop()); return; }
      stream.current = media;
      const next = new MediaRecorder(media, { mimeType });
      recorder.current = next;
      const chunks: Blob[] = [];
      let size = 0;
      let failed = false;
      next.ondataavailable = event => {
        if (event.data.size) { chunks.push(event.data); size += event.data.size; }
        if (size > 10 * 1024 * 1024) {
          failed = true; setError("Recording exceeds 10 MB. Please record a shorter answer.");
          if (next.state === "recording") next.stop();
        }
      };
      next.onerror = () => {
        failed = true;
        if (mounted.current) { setError("Recording failed. Please try again."); setRecording(false); onBusy(false); }
        media.getTracks().forEach(track => track.stop());
      };
      next.onstop = () => {
        media.getTracks().forEach(track => track.stop());
        if (!mounted.current) return;
        setRecording(false); onBusy(false);
        setSeconds(Math.min(600, (Date.now() - started.current) / 1000));
        if (!failed && size) setClip(new Blob(chunks, { type: next.mimeType }));
        else if (!failed) setError("No audio was captured. Please re-record.");
      };
      started.current = Date.now(); setSeconds(0);
      next.start(1000); setRecording(true);
    } catch (err) {
      stream.current?.getTracks().forEach(track => track.stop());
      if (!mounted.current) return;
      const name = err instanceof DOMException ? err.name : "";
      setError(name === "NotAllowedError" ? "Microphone permission denied. Allow access in browser settings and try again."
        : name === "NotFoundError" ? "No microphone found. Connect one and try again."
        : "Unable to record. Check that your microphone is connected and available.");
      onBusy(false);
    } finally {
      starting.current = false;
      if (mounted.current) setRequesting(false);
    }
  }

  return <div className="space-y-3">
    <p role="status">{requesting ? "Waiting for microphone permission..." : recording ? "Recording" : clip ? "Recording ready" : "Record your spoken answer (up to 10 minutes / 10 MB)."}
      {(recording || clip) && ` ${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`}</p>
    {error && <Alert>{error}</Alert>}
    {url && <audio controls src={url} aria-label="Replay your recorded answer" />}
    <div className="flex flex-wrap gap-2">
      {!recording && <Button onClick={start} disabled={disabled || requesting}>{clip ? "Re-record" : "Record Audio"}</Button>}
      {recording && <Button onClick={() => { if (recorder.current?.state === "recording") recorder.current.stop(); }}>Stop recording</Button>}
      {clip && <>
        <Button variant="secondary" disabled={disabled} onClick={() => { setClip(null); setSeconds(0); }}>Discard</Button>
        <Button disabled={disabled} onClick={() => onSubmit(clip, seconds)}>Submit Audio Answer</Button>
      </>}
    </div>
  </div>;
}
