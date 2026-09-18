# Audio interview answers

The Next.js interview session displays text questions. Select Audio, click Record Audio,
allow microphone access, speak, Stop, and optionally replay, discard, or re-record.
Submit Audio Answer uploads and transcribes, shows the saved transcript, and invokes
the existing evaluation endpoint. Evaluation failure leaves the transcript saved;
Retry evaluation does not repeat transcription. Text submission remains available.

## Browser recording

`AudioAnswerRecorder` requests microphone access only on click. MediaRecorder selects
WebM/Opus, WebM, MP4, or Ogg/Opus using browser support detection. A timer, permission
and recording errors, playback controls, and a submission lock cover the lifecycle.
Tracks stop on completion/unmount; object URLs are revoked. Recording stops at ten
minutes or 10 MB. HTTPS or localhost is required. No TTS or video analysis is added.

## API and data

`POST /api/v1/interviews/{interview_id}/questions/{question_id}/audio-answer`
accepts multipart `audio` and optional `duration_seconds` (0?600; client-reported).
It retains existing Premium authentication and application/interview ownership checks.
Response uses the existing answer envelope, including answer_id, answer_text (the
transcript), source=voice, duration_seconds, audio_mime_type, and audio_size_bytes.
No filesystem path is exposed. The frontend then calls the unchanged
`POST /api/v1/interviews/{interview_id}/answers/{answer_id}/evaluate`.
The evaluator reads answer_text, and build_adaptation_context reads its evaluation
as before. Question generation and adaptive code are unchanged.

Migration `0009_interview_audio` adds nullable audio_storage_key, audio_mime_type,
and audio_size_bytes to interview_answers. Existing source, answer_text, duration,
and created_at are reused. Transcription is synchronous: only successful transcripts
are persisted; no pending/failed answer rows or redundant status field is needed.
Both text and audio use the same row update helper. PostgreSQL question row locks
serialize replacements, preserving the existing one-answer-per-question behavior.
Retries replace the answer in place and clear stale evaluation. SQLite does not
provide PostgreSQL row-lock concurrency guarantees.

## Storage and STT

Audio is private under STORAGE_LOCAL_DIR/interview_audio/{interview_id}/{uuid}.ext,
following the existing local storage configuration. Original filenames are ignored.
The default limit is 10 MB (INTERVIEW_AUDIO_MAX_MB); reads are bounded and MIME types
are checked against container signatures. The provider performs decoding; signature
checks are not a complete media decoder. Configure an ingress request-size limit
in production as multipart parsing happens before endpoint validation.
Replaced recordings and failed DB writes are cleaned up. Interview/application
removal does not currently purge orphaned recordings: configure retention cleanup
before production. There is no server playback/download endpoint; replay uses the
browser recording before submission. Cloud storage is not implemented.

The existing google-genai==0.7.0 dependency and GEMINI_API_KEY are used. Optional
GEMINI_TRANSCRIPTION_MODEL overrides GEMINI_MODEL for transcription only. No new
key or local model is introduced. The provider has a bounded request timeout;
missing config, provider failure, empty speech, and oversized transcripts return
errors without inventing fallback text. Audio is sent to Gemini on submission.
See https://ai.google.dev/gemini-api/docs/generate-content/audio.

## Local verification

1. Install backend requirements in a compatible Python environment. The supplied
   Python 3.14 environment cannot build the pinned PyMuPDF without Visual Studio;
   this is unrelated to audio. google-genai can be installed separately if needed.
2. In the backend working directory configure GEMINI_API_KEY, GEMINI_MODEL (or
   GEMINI_TRANSCRIPTION_MODEL), STORAGE_BACKEND=local and STORAGE_LOCAL_DIR.
3. Run `python -m alembic upgrade head` from backend, then start the existing API
   and frontend (`npm run dev`). Migration is not applied to your live DB by this change.
4. Sign in with a Premium user, open an application interview, generate a question,
   record and replay an answer, submit, verify transcript and evaluation, then
   proceed through question 3 to exercise adaptation. Try denial, discard/re-record,
   text replacement, and retry after a provider/evaluation error.
5. Automated: `python -m pytest tests/test_interview_audio.py tests/test_interviews.py -q`.
   STT is mocked; fixtures contain synthetic bytes, never committed recordings.
   Frontend: `npm run build` and `npx tsc --noEmit`.

Live microphone and real-provider accuracy require manual browser testing; automated
endpoint tests do not assess speech recognition quality.
