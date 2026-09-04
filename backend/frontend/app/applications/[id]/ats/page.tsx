"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AnalysisReport, type AnalysisView } from "@/components/analysis-report";
import { ScanPanel } from "@/components/scan-panel";
import { Card, CardHeader, Skeleton } from "@/components/ui";
import { getApplication, type Application } from "@/lib/applications";
import { analyzeResume, getVersions, uploadResume, type AnalyzeData } from "@/lib/resumes";

export default function AtsPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const [app, setApp] = useState<Application | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisView | null>(null);
  const [resume, setResume] = useState<{ resume_id: string; version_number: number; skills: string[] } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    Promise.all([getApplication(id), getVersions(id)])
      .then(([application, versions]) => {
        setApp(application);
        // Pick up where the last session left off: newest version and its report.
        const latest = versions.data.versions.at(-1);
        if (latest) {
          setResume({
            resume_id: latest.resume_id,
            version_number: latest.version_number,
            skills: latest.parsed_data.skills,
          });
        }
      })
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [id]);

  const upload = useCallback((file: File) => uploadResume(id!, file), [id]);
  const analyze = useCallback(
    (resumeId: string, jd: { text?: string; file?: File }) => analyzeResume(id!, resumeId, jd),
    [id],
  );

  function onAnalyzed(data: AnalyzeData) {
    setAnalysis(data);
    requestAnimationFrame(() => document.getElementById("ats-result")?.scrollIntoView({ behavior: "smooth" }));
  }

  if (loading) return <Skeleton className="h-96" />;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Resume & ATS"
          description="Score a resume for this role. Each upload becomes a new version you can compare later."
        />
        <div className="p-6">
          <ScanPanel
            upload={upload}
            analyze={analyze}
            initialResume={resume}
            initialJobDescription={app?.job_description ?? null}
            onAnalyzed={onAnalyzed}
          />
        </div>
      </Card>

      {analysis ? (
        <section id="ats-result" className="scroll-mt-24">
          <AnalysisReport analysis={analysis} />
        </section>
      ) : null}
    </div>
  );
}
