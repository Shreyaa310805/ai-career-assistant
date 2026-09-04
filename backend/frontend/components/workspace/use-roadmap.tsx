"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Card, EmptyState, LinkButton, Skeleton } from "@/components/ui";
import { getCareerRoadmap, type CareerRoadmap } from "@/lib/career";

/**
 * Every career tool reads the same roadmap payload, which needs an uploaded
 * resume and a completed ATS analysis. The hook centralises that dependency so
 * each tab shows the same, actionable prerequisite message instead of a raw
 * 409.
 */
export function useRoadmap() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const [roadmap, setRoadmap] = useState<CareerRoadmap | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    setLoading(true);
    getCareerRoadmap(id, controller.signal)
      .then(setRoadmap)
      .catch((requestError: Error) => {
        if (!controller.signal.aborted) setError(requestError.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [id]);

  return { applicationId: id, roadmap, error, loading };
}

export function RoadmapGate({
  loading,
  error,
  applicationId,
}: {
  loading: boolean;
  error: string;
  applicationId?: string;
}) {
  if (loading) return <Skeleton className="h-72" />;
  return (
    <Card>
      <EmptyState
        title="Analyse a resume first"
        description={
          error ||
          "Upload a resume for this role and run an ATS analysis — the career tools are built from that result."
        }
        action={
          applicationId ? (
            <LinkButton href={`/applications/${applicationId}/ats`}>Go to Resume &amp; ATS</LinkButton>
          ) : undefined
        }
      />
    </Card>
  );
}
