import { Badge, type Tone } from "@/components/ui";
import { STATUS_LABEL, type Status } from "@/lib/applications";

const STATUS_TONE: Record<Status, Tone> = {
  SAVED: "neutral",
  APPLIED: "info",
  INTERVIEWING: "warning",
  SELECTED: "success",
  OFFER: "success",
  OFFER_DECLINED: "neutral",
  REJECTED: "danger",
};

export function StatusBadge({ status, className }: { status: Status; className?: string }) {
  return (
    <Badge tone={STATUS_TONE[status]} className={className}>
      {STATUS_LABEL[status]}
    </Badge>
  );
}
