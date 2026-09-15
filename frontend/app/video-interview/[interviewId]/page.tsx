"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Badge, Button, Skeleton, cx } from "@/components/ui";
import { ApiRequestError, getToken } from "@/lib/auth";
import { getApplication } from "@/lib/applications";
import {
  completeInterview,
  evaluateInterviewAnswer,
  generateInterviewQuestion,
  getInterviewFull,
  submitInterviewAudio,
  submitVisualFrame,
  type InterviewAnswerEvaluation,
  type InterviewDifficulty,
  type InterviewPersonality,
  type InterviewQuestion,
} from "@/lib/interviews";

const PERSONALITY_LABEL: Record<InterviewPersonality, string> = {
  technical: "Technical",
  friendly: "Friendly",
  strict: "Strict",
  behavioral: "Behavioral",
  mixed: "Mixed",
};
const DIFFICULTY_LABEL: Record<InterviewDifficulty, string> = { easy: "Easy", medium: "Medium", hard: "Hard" };

const MAX_ANSWER_SECONDS = 600;
const MAX_ANSWER_BYTES = 10 * 1024 * 1024;
const FRAME_WIDTH = 480;

type CameraState = "idle" | "requesting" | "live" | "error";
type AnswerPhase = "idle" | "recording" | "submitting";

const randomBetween = (min: number, max: number) => min + Math.random() * (max - min);

function describeMediaError(err: unknown) {
  const name = err instanceof DOMException ? err.name : "";
  if (name === "NotAllowedError" || name === "SecurityError")
    return "Camera and microphone access was blocked. Allow access in your browser's site settings, then try again.";
  if (name === "NotFoundError" || name === "OverconstrainedError")
    return "No camera or microphone was found. Connect one and try again.";
  if (name === "NotReadableError" || name === "AbortError")
    return "Your camera or microphone is in use by another application. Close it and try again.";
  return "Unable to start your camera. Check your devices and try again.";
}

function formatClock(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}

export default function VideoInterviewPage() {
  const params = useParams<{ interviewId: string }>();
  const router = useRouter();
  const interviewId = params?.interviewId;

  const [isLoading, setIsLoading] = useState(true);
  const [isVideoSession, setIsVideoSession] = useState(false);
  const [error, setError] = useState("");
  const [applicationId, setApplicationId] = useState<string | null>(null);
  const [company, setCompany] = useState<string | null>(null);
  const [personality, setPersonality] = useState<InterviewPersonality>("technical");
  const [difficulty, setDifficulty] = useState<InterviewDifficulty>("medium");
  const [questionTarget, setQuestionTarget] = useState(5);
  const [answeredCount, setAnsweredCount] = useState(0);

  const [question, setQuestion] = useState<InterviewQuestion | null>(null);
  const [answerId, setAnswerId] = useState<string | null>(null);
  const [answerText, setAnswerText] = useState("");
  const [evaluation, setEvaluation] = useState<InterviewAnswerEvaluation | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [isEnding, setIsEnding] = useState(false);

  const [stream, setStream] = useState<MediaStream | null>(null);
  const [cameraState, setCameraState] = useState<CameraState>("idle");
  const [cameraError, setCameraError] = useState("");
  const [answerPhase, setAnswerPhase] = useState<AnswerPhase>("idle");
  const [seconds, setSeconds] = useState(0);
  const [framesAnalyzed, setFramesAnalyzed] = useState(0);
  const [visualNotice, setVisualNotice] = useState("");

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const discardRecordingRef = useRef(false);
  const recordingStartedRef = useRef(0);
  const questionIdRef = useRef<string | null>(null);
  const frameUploadRef = useRef<Promise<unknown> | null>(null);
  const mountedRef = useRef(true);

  const stopMedia = useCallback(() => {
    discardRecordingRef.current = true;
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    recorderRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    if (mountedRef.current) {
      setStream(null);
      setCameraState("idle");
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    const onPageHide = () => stopMedia();
    window.addEventListener("pagehide", onPageHide);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      mountedRef.current = false;
      stopMedia();
    };
  }, [stopMedia]);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    if (!interviewId) return;
    getInterviewFull(interviewId)
      .then(async (response) => {
        if (!response.success || !response.data) {
          setError(response.error?.message ?? "Unable to load this interview session.");
          return;
        }
        const full = response.data;
        setApplicationId(full.application_id);
        if (full.status === "completed") {
          router.replace(`/applications/${full.application_id}/interview/${interviewId}`);
          return;
        }
        if (full.mode !== "video") {
          router.replace(`/interview-session/${interviewId}`);
          return;
        }
        setPersonality(full.personality);
        setDifficulty(full.difficulty);
        setQuestionTarget(full.question_target);
        setAnsweredCount(full.items.filter((item) => item.evaluation).length);
        const last = full.items[full.items.length - 1];
        if (last) {
          setQuestion(last.question);
          setAnswerId(last.answer?.answer_id ?? null);
          setAnswerText(last.answer?.answer_text ?? "");
          setEvaluation(last.evaluation);
        }
        setIsVideoSession(true);
        getApplication(full.application_id)
          .then((application) => setCompany(application.company))
          .catch(() => undefined);
      })
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interviewId]);

  const startCamera = useCallback(async () => {
    if (streamRef.current) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraState("error");
      setCameraError("Camera access is unavailable in this browser. Use a current browser over HTTPS or localhost.");
      return;
    }
    setCameraState("requesting");
    setCameraError("");
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      if (!mountedRef.current) {
        media.getTracks().forEach((track) => track.stop());
        return;
      }
      discardRecordingRef.current = false;
      streamRef.current = media;
      media.getVideoTracks()[0]?.addEventListener("ended", () => {
        if (streamRef.current !== media || !mountedRef.current) return;
        stopMedia();
        setCameraState("error");
        setCameraError("Your camera disconnected. Reconnect it to continue the interview.");
      });
      // The <video> element is always mounted, so the stream is attached in the effect below.
      setStream(media);
    } catch (err) {
      if (!mountedRef.current) return;
      setCameraState("error");
      setCameraError(describeMediaError(err));
    }
  }, [stopMedia]);

  // Camera access is requested only once the session is confirmed to be a video interview.
  useEffect(() => {
    if (isVideoSession) void startCamera();
  }, [isVideoSession, startCamera]);

  useEffect(() => {
    const element = videoRef.current;
    if (!element || !stream) return;
    element.srcObject = stream;
    element.play().catch(() => {
      // Autoplay of a muted inline video is permitted; onPlaying still flips the state if play resolves later.
    });
    return () => {
      if (element.srcObject === stream) element.srcObject = null;
    };
    // isLoading: the <video> mounts only after loading, and the stream may already exist by then.
  }, [stream, isLoading]);

  useEffect(() => {
    questionIdRef.current = question?.question_id ?? null;
  }, [question]);

  useEffect(() => {
    if (answerPhase !== "recording") return;
    const timer = window.setInterval(() => {
      const elapsed = (Date.now() - recordingStartedRef.current) / 1000;
      setSeconds(Math.min(MAX_ANSWER_SECONDS, elapsed));
      if (elapsed >= MAX_ANSWER_SECONDS && recorderRef.current?.state === "recording") recorderRef.current.stop();
    }, 250);
    return () => window.clearInterval(timer);
  }, [answerPhase]);

  const cameraLive = cameraState === "live";
  const captureActive = isVideoSession && cameraLive && Boolean(question) && !isEnding && !visualNotice;

  // Random-interval frame sampling, strictly scoped to an active, started video interview.
  useEffect(() => {
    if (!captureActive || !interviewId) return;
    let cancelled = false;
    let timer: number | undefined;

    const schedule = (first: boolean) => {
      if (cancelled) return;
      timer = window.setTimeout(capture, first ? randomBetween(4000, 12000) : randomBetween(15000, 35000));
    };

    const capture = async () => {
      if (cancelled) return;
      const video = videoRef.current;
      if (document.visibilityState !== "visible" || !video || video.readyState < 2 || !video.videoWidth) {
        schedule(false);
        return;
      }
      const canvas = canvasRef.current ?? (canvasRef.current = document.createElement("canvas"));
      canvas.width = FRAME_WIDTH;
      canvas.height = Math.round((video.videoHeight / video.videoWidth) * FRAME_WIDTH);
      canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.75));
      if (cancelled || !blob) return;
      const upload = submitVisualFrame(interviewId, blob, questionIdRef.current ?? undefined);
      frameUploadRef.current = upload;
      try {
        const response = await upload;
        if (!cancelled && response.data) setFramesAnalyzed(response.data.frames_analyzed);
      } catch (err) {
        const status = err instanceof ApiRequestError ? err.status : 0;
        if (status === 503) {
          if (!cancelled) setVisualNotice("Visual analysis isn't configured on the server, so no presence score will be generated.");
          return;
        }
        if (status === 409 || status === 429 || status === 401 || status === 403 || status === 404) return;
      } finally {
        if (frameUploadRef.current === upload) frameUploadRef.current = null;
      }
      schedule(false);
    };

    schedule(true);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [captureActive, interviewId]);

  const questionsAsked = question ? question.question_number : 0;
  const atTarget = questionsAsked >= questionTarget;
  const answerSubmitted = Boolean(answerId);
  const busy = isGenerating || answerPhase !== "idle" || isEvaluating || isEnding;

  async function generateQuestion() {
    if (!interviewId || busy) return;
    setError("");
    setIsGenerating(true);
    try {
      const response = await generateInterviewQuestion(interviewId);
      if (!response.success || !response.data) {
        setError(response.error?.message ?? "Unable to generate a question. Please try again.");
        return;
      }
      setQuestion(response.data);
      setAnswerId(null);
      setAnswerText("");
      setEvaluation(null);
      setSeconds(0);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to generate a question. Please try again.");
    } finally {
      setIsGenerating(false);
    }
  }

  async function evaluate(savedAnswerId: string) {
    if (!interviewId) return;
    setIsEvaluating(true);
    try {
      const evaluated = await evaluateInterviewAnswer(interviewId, savedAnswerId);
      if (!evaluated.success || !evaluated.data) throw new Error(evaluated.error?.message ?? "Unable to evaluate answer.");
      setEvaluation(evaluated.data);
      setAnsweredCount((count) => count + 1);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? `Your answer was saved, but scoring failed: ${requestError.message}`
          : "Your answer was saved, but scoring failed. Retry scoring.",
      );
    } finally {
      if (mountedRef.current) setIsEvaluating(false);
    }
  }

  async function submitRecording(blob: Blob, duration: number) {
    if (!interviewId || !question) return;
    setAnswerPhase("submitting");
    try {
      const submitted = await submitInterviewAudio(interviewId, question.question_id, blob, Math.round(duration));
      if (!submitted.success || !submitted.data) throw new Error(submitted.error?.message ?? "Unable to save answer.");
      setAnswerId(submitted.data.answer_id);
      setAnswerText(submitted.data.answer_text);
      setAnswerPhase("idle");
      await evaluate(submitted.data.answer_id);
    } catch (requestError) {
      // Nothing was saved (e.g. no intelligible speech), so answering this question is still open.
      setError(requestError instanceof Error ? requestError.message : "Unable to submit your answer. Please answer again.");
      setAnswerPhase("idle");
    }
  }

  function startAnswer() {
    const media = streamRef.current;
    if (!media || !question || answerSubmitted || busy) return;
    const audioTracks = media.getAudioTracks().filter((track) => track.readyState === "live");
    if (!audioTracks.length) {
      setError("No microphone is available. Reconnect it to answer.");
      return;
    }
    if (typeof MediaRecorder === "undefined") {
      setError("Recording isn't supported in this browser.");
      return;
    }
    const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"].find((type) =>
      MediaRecorder.isTypeSupported(type),
    );
    if (!mimeType) {
      setError("This browser has no supported audio recording format.");
      return;
    }
    setError("");
    // Record only the audio tracks; stopping the recorder must not stop the shared camera stream.
    const recorder = new MediaRecorder(new MediaStream(audioTracks), { mimeType });
    const chunks: Blob[] = [];
    let size = 0;
    let failed = false;
    discardRecordingRef.current = false;
    recorder.ondataavailable = (event) => {
      if (event.data.size) {
        chunks.push(event.data);
        size += event.data.size;
      }
      if (size > MAX_ANSWER_BYTES && recorder.state === "recording") {
        recorder.stop();
      }
    };
    recorder.onerror = () => {
      failed = true;
    };
    recorder.onstop = () => {
      recorderRef.current = null;
      if (discardRecordingRef.current || !mountedRef.current) return;
      const duration = (Date.now() - recordingStartedRef.current) / 1000;
      setSeconds(Math.min(MAX_ANSWER_SECONDS, duration));
      if (failed || !size) {
        setAnswerPhase("idle");
        setError("No audio was captured. Please answer again.");
        return;
      }
      void submitRecording(new Blob(chunks, { type: recorder.mimeType }), Math.min(MAX_ANSWER_SECONDS, duration));
    };
    recorderRef.current = recorder;
    recordingStartedRef.current = Date.now();
    setSeconds(0);
    recorder.start(1000);
    setAnswerPhase("recording");
  }

  function finishAnswer() {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }

  async function endSession() {
    if (!interviewId || !applicationId || isEnding || answerPhase !== "idle") return;
    setError("");
    setIsEnding(true);
    stopMedia();
    // Let an in-flight frame land before the server aggregates the visual score.
    if (frameUploadRef.current) {
      await Promise.race([frameUploadRef.current.catch(() => undefined), new Promise((r) => setTimeout(r, 10000))]);
    }
    try {
      const response = await completeInterview(interviewId);
      if (!response.success || !response.data) throw new Error(response.error?.message ?? "Unable to end this session.");
      router.push(`/applications/${applicationId}/interview/${interviewId}`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to end this session. Please try again.");
      setIsEnding(false);
    }
  }

  function leave() {
    stopMedia();
    router.push(applicationId ? `/applications/${applicationId}/interview` : "/dashboard");
  }

  const statusLabel =
    answerPhase === "recording"
      ? "Recording answer"
      : answerPhase === "submitting"
        ? "Transcribing answer…"
        : isEvaluating
          ? "Scoring answer…"
          : isGenerating
            ? "Preparing question…"
            : null;

  return (
    <main className="flex min-h-screen flex-col bg-slate-950 text-slate-100">
      <header className="border-b border-white/10 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-lg font-bold tracking-tight text-white">
              Skill<span className="text-brand-400">Sync</span>
            </Link>
            <span className="hidden h-6 w-px bg-white/15 sm:block" />
            <div className="leading-tight">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-300">Video interview</p>
              <p className="text-sm text-slate-300">
                {company ? `${company} · ` : ""}
                {PERSONALITY_LABEL[personality]} · {DIFFICULTY_LABEL[difficulty]}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="text-slate-300 hover:bg-white/10 hover:text-white"
              onClick={leave}
              disabled={isEnding || answerPhase !== "idle"}
            >
              Leave
            </Button>
            <Button
              size="sm"
              className="bg-rose-600 hover:bg-rose-700 active:bg-rose-800"
              onClick={endSession}
              disabled={isLoading || !isVideoSession || isEnding || answerPhase !== "idle" || isEvaluating}
            >
              {isEnding ? "Ending…" : "End interview"}
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-4 px-4 py-4 sm:px-6">
        {isLoading ? (
          <>
            <Skeleton className="h-[64vh] w-full rounded-2xl bg-white/5" />
            <Skeleton className="h-40 w-full rounded-2xl bg-white/5" />
          </>
        ) : !isVideoSession ? (
          <div className="mx-auto mt-16 max-w-md space-y-4 rounded-2xl bg-white p-6 text-slate-900">
            <Alert>{error || "Unable to open this video interview."}</Alert>
            <Button variant="secondary" onClick={leave}>
              Go back
            </Button>
          </div>
        ) : (
          <>
            <section
              className="relative h-[56vh] min-h-[300px] overflow-hidden rounded-2xl border border-white/10 bg-black shadow-2xl sm:h-[64vh]"
              aria-label="Your camera"
            >
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                onPlaying={() => setCameraState("live")}
                className={cx(
                  "h-full w-full -scale-x-100 object-cover transition-opacity duration-300",
                  cameraLive ? "opacity-100" : "opacity-0",
                )}
              />

              {!cameraLive ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-slate-900 px-6 text-center">
                  {cameraState === "error" ? (
                    <>
                      <p className="max-w-md text-sm text-slate-300">{cameraError}</p>
                      <Button onClick={() => void startCamera()}>Try again</Button>
                    </>
                  ) : isEnding ? (
                    <p className="text-sm text-slate-400">Camera off. Wrapping up your interview…</p>
                  ) : (
                    <>
                      <span className="h-10 w-10 animate-spin rounded-full border-2 border-white/20 border-t-brand-400" />
                      <p className="text-sm text-slate-300">
                        {stream ? "Starting camera…" : "Waiting for camera and microphone permission…"}
                      </p>
                    </>
                  )}
                </div>
              ) : null}

              <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-3 p-3 sm:p-4">
                <span className="flex items-center gap-2 rounded-full bg-black/55 px-3 py-1 text-xs font-medium text-white backdrop-blur">
                  <span className={cx("h-2 w-2 rounded-full", cameraLive ? "bg-emerald-400" : "bg-slate-500")} />
                  {cameraLive ? "Camera on" : "Camera off"}
                </span>
                <span className="rounded-full bg-black/55 px-3 py-1 text-xs font-medium text-white backdrop-blur">
                  {question ? `Question ${question.question_number} of ${questionTarget}` : `${questionTarget} questions`}
                </span>
              </div>

              {answerPhase === "recording" ? (
                <div className="pointer-events-none absolute bottom-3 left-3 flex items-center gap-2 rounded-full bg-rose-600/90 px-3 py-1.5 text-sm font-semibold text-white sm:bottom-4 sm:left-4">
                  <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-white" />
                  REC {formatClock(seconds)}
                </div>
              ) : statusLabel ? (
                <div className="pointer-events-none absolute bottom-3 left-3 rounded-full bg-black/60 px-3 py-1.5 text-sm text-white sm:bottom-4 sm:left-4">
                  {statusLabel}
                </div>
              ) : null}
            </section>

            <section className="rounded-2xl bg-white p-5 text-slate-900 shadow-xl sm:p-6">
              {error ? (
                <div className="mb-4">
                  <Alert>{error}</Alert>
                </div>
              ) : null}

              <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
                <div className="min-w-0">
                  {question ? (
                    <>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone="brand">{question.topic}</Badge>
                        <Badge>{DIFFICULTY_LABEL[question.difficulty]}</Badge>
                        <Badge tone="neutral">{question.question_type.replace(/_/g, " ")}</Badge>
                      </div>
                      <p className="mt-3 text-lg font-medium leading-8 text-slate-900 sm:text-xl">{question.question}</p>
                    </>
                  ) : (
                    <>
                      <h1 className="text-xl font-semibold">Ready for your video interview?</h1>
                      <p className="mt-2 text-sm leading-6 text-slate-600">
                        Check that your face is centered and well lit. Answer each question out loud — once you finish an
                        answer it's submitted and can't be redone. While the interview runs, a few camera frames are sampled
                        at random moments to score on-camera presence; the images themselves aren't stored.
                      </p>
                    </>
                  )}

                  {answerSubmitted ? (
                    <div className="mt-5 rounded-lg border border-line bg-surface-muted/60 p-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Your answer (transcript)</p>
                      <p className="mt-1.5 max-h-32 overflow-y-auto whitespace-pre-wrap text-sm leading-6 text-slate-700">
                        {answerText}
                      </p>
                    </div>
                  ) : null}

                  {evaluation ? (
                    <p className="mt-4 text-sm text-slate-500">Answer saved and evaluated. Your feedback will appear in the final session summary.</p>
                  ) : null}
                </div>

                <div className="flex flex-col gap-3 border-t border-line pt-5 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span>Progress</span>
                    <span>
                      {answeredCount}/{questionTarget} answered
                    </span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-sunken">
                    <div
                      className="h-full rounded-full bg-brand-600 transition-all"
                      style={{ width: `${Math.min(100, (answeredCount / questionTarget) * 100)}%` }}
                    />
                  </div>

                  {!question ? (
                    <Button size="lg" onClick={generateQuestion} disabled={!cameraLive || busy}>
                      {isGenerating ? "Preparing…" : "Start interview"}
                    </Button>
                  ) : answerPhase === "recording" ? (
                    <Button size="lg" className="bg-rose-600 hover:bg-rose-700" onClick={finishAnswer}>
                      Finish answer · {formatClock(seconds)}
                    </Button>
                  ) : !answerSubmitted ? (
                    <Button size="lg" onClick={startAnswer} disabled={!cameraLive || busy}>
                      {answerPhase === "submitting" ? "Submitting…" : "Start answering"}
                    </Button>
                  ) : !evaluation ? (
                    <Button size="lg" onClick={() => answerId && void evaluate(answerId)} disabled={busy}>
                      {isEvaluating ? "Scoring…" : "Retry scoring"}
                    </Button>
                  ) : !atTarget ? (
                    <Button size="lg" onClick={generateQuestion} disabled={!cameraLive || busy}>
                      {isGenerating ? "Preparing…" : "Next question"}
                    </Button>
                  ) : (
                    <Button size="lg" onClick={endSession} disabled={busy}>
                      {isEnding ? "Ending…" : "Finish & see results"}
                    </Button>
                  )}

                  <p className="text-xs leading-5 text-slate-500">
                    {!cameraLive && !isEnding
                      ? "Your camera needs to be on to continue."
                      : answerPhase === "recording"
                        ? `Speak your answer, then select Finish. Limit ${MAX_ANSWER_SECONDS / 60} minutes.`
                        : question && !answerSubmitted
                          ? "Answers are final once finished — take a moment to think first."
                          : atTarget && evaluation
                            ? "That was the last question."
                            : null}
                  </p>
                  <p className="text-xs text-slate-400">
                    {visualNotice
                      ? visualNotice
                      : captureActive
                        ? `Presence analysis active${framesAnalyzed ? ` · ${framesAnalyzed} frame${framesAnalyzed === 1 ? "" : "s"} analyzed` : ""}`
                        : question
                          ? "Presence analysis paused."
                          : "Presence analysis starts with the first question."}
                  </p>
                </div>
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
