"use client";
import { useParams } from "next/navigation";
import InterviewPractice from "@/components/interview-practice";
export default function InterviewPage() {
  const params = useParams<{ id: string }>();
  return <InterviewPractice applicationId={params?.id} />;
}
