"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Alert, Badge, Button, Card, CardHeader, EmptyState, LinkButton, Skeleton } from "@/components/ui";
import { deleteInterview, listInterviews, type InterviewSummary } from "@/lib/interviews";

const PAGE_SIZE = 10;

const STATUS_TONE = {
  created: "neutral",
  in_progress: "info",
  completed: "success",
} as const;

const STATUS_LABEL = {
  created: "Not started",
  in_progress: "In progress",
  completed: "Completed",
} as const;

export default function InterviewHistoryPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const applicationId = params?.id;
  const [items, setItems] = useState<InterviewSummary[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!applicationId) return;
    listInterviews(applicationId, page, PAGE_SIZE)
      .then((response) => {
        if (!response.success || !response.data) {
          setError(response.error?.message ?? "Unable to load past interview sessions.");
          return;
        }
        setItems(response.data.items);
        setTotal(response.data.total);
      })
      .catch((requestError: Error) => setError(requestError.message));
  }, [applicationId, page]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleDelete(interviewId: string) {
    if (!confirm("Delete this interview session? This cannot be undone.")) return;
    setError("");
    setDeletingId(interviewId);
    try {
      const response = await deleteInterview(interviewId);
      if (!response.success) {
        setError(response.error?.message ?? "Unable to delete this session. Please try again.");
        return;
      }
      load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to delete this session. Please try again.");
    } finally {
      setDeletingId(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <Card>
      <CardHeader
        title="Past interview sessions"
        description="Review scores, confidence, and feedback from sessions you've already run for this application."
        action={
          <LinkButton href={`/applications/${applicationId}/interview`} variant="secondary" size="sm">
            Back to practice
          </LinkButton>
        }
      />
      <div className="space-y-4 p-6">
        {error ? <Alert>{error}</Alert> : null}
        {items === null ? (
          <div className="space-y-3">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            title="No sessions yet"
            description="Start a practice interview to see it listed here for review."
            action={
              <LinkButton href={`/applications/${applicationId}/interview`}>Start an interview</LinkButton>
            }
          />
        ) : (
          <ul className="space-y-3">
            {items.map((item) => {
              const isComplete = item.status === "completed";
              const target = item.question_target || item.question_count;
              return (
                <li
                  key={item.interview_id}
                  className="rounded-lg border border-line p-4 transition-colors hover:border-line-strong hover:bg-surface-muted"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <button
                      type="button"
                      className="min-w-0 flex-1 text-left"
                      onClick={() =>
                        router.push(
                          isComplete
                            ? `/applications/${applicationId}/interview/${item.interview_id}`
                            : `/interview-session/${item.interview_id}`,
                        )
                      }
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={STATUS_TONE[item.status]}>{STATUS_LABEL[item.status]}</Badge>
                        <Badge tone="brand">{item.personality}</Badge>
                        <Badge>{item.difficulty}</Badge>
                      </div>
                      <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-slate-600">
                        <span>
                          {item.answered_count}/{target} answered
                        </span>
                        {item.average_score !== null ? <span>Avg score {Math.round(item.average_score)}/100</span> : null}
                        {item.average_confidence !== null ? (
                          <span>Avg confidence {Math.round(item.average_confidence)}/100</span>
                        ) : null}
                        <span className="text-slate-400">{new Date(item.created_at).toLocaleDateString()}</span>
                      </div>
                    </button>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      {isComplete ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => router.push(`/applications/${applicationId}/interview/${item.interview_id}`)}
                        >
                          View results
                        </Button>
                      ) : (
                        <Button size="sm" onClick={() => router.push(`/interview-session/${item.interview_id}`)}>
                          Resume
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-rose-700 hover:bg-rose-50"
                        onClick={() => handleDelete(item.interview_id)}
                        disabled={deletingId === item.interview_id}
                      >
                        {deletingId === item.interview_id ? "Deleting…" : "Delete"}
                      </Button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        {items && total > PAGE_SIZE ? (
          <div className="flex items-center justify-between border-t border-line pt-4">
            <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <span className="text-sm text-slate-500">
              Page {page} of {totalPages}
            </span>
            <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Next
            </Button>
          </div>
        ) : null}
      </div>
    </Card>
  );
}
