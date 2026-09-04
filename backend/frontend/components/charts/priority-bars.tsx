"use client";

import { useState } from "react";
import { Badge, type Tone } from "@/components/ui";
import type { Priority } from "@/lib/career";

/**
 * Missing skills ranked by how much closing them would matter for this role.
 *
 * One measure (priority score) across nominal skills, so every bar takes the
 * same series colour. Priority is carried by a written badge next to the bar,
 * not by hue, and the reason appears on hover/focus instead of as a paragraph
 * under each row.
 */
export type PrioritySkill = { skill: string; priority: Priority; priority_score: number; reason: string };

const PRIORITY_TONE: Record<Priority, Tone> = { High: "danger", Medium: "warning", Low: "success" };

export function PriorityBars({ skills }: { skills: PrioritySkill[] }) {
  const [active, setActive] = useState<string | null>(null);

  if (skills.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        Nothing outstanding — your resume already evidences every skill this role asks for.
      </p>
    );
  }

  const ranked = [...skills].sort((a, b) => b.priority_score - a.priority_score);

  return (
    <ul className="space-y-1">
      {ranked.map((item) => {
        const pct = Math.round(item.priority_score * 100);
        const isActive = active === item.skill;
        return (
          <li
            key={item.skill}
            className="rounded-lg px-3 py-2.5 transition-colors hover:bg-surface-muted"
            onMouseEnter={() => setActive(item.skill)}
            onMouseLeave={() => setActive(null)}
            onFocus={() => setActive(item.skill)}
            onBlur={() => setActive(null)}
            tabIndex={0}
          >
            <div className="flex items-center justify-between gap-4">
              <span className="truncate text-sm font-medium text-slate-800">{item.skill}</span>
              <div className="flex shrink-0 items-center gap-3">
                <span className="text-sm text-slate-500 tabular-nums">{pct}</span>
                <Badge tone={PRIORITY_TONE[item.priority]}>{item.priority}</Badge>
              </div>
            </div>
            <div
              className="mt-2 h-1.5 w-full overflow-hidden rounded-full"
              style={{ background: "var(--viz-track)" }}
              role="img"
              aria-label={`${item.skill}: ${item.priority} priority, score ${pct} of 100`}
            >
              <div
                className="h-full rounded-full"
                style={{
                  width: `${pct}%`,
                  background: "var(--viz-series-1)",
                  transition: "width 600ms cubic-bezier(0.16, 1, 0.3, 1)",
                }}
              />
            </div>
            {isActive ? (
              <p className="mt-2 text-xs leading-5 text-slate-500 animate-fade-up">{item.reason}</p>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
