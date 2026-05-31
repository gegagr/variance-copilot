import { useState } from "react";

import type { FlaggedVarianceView, ReviewItemView, ReviewStatus } from "@/api/schema";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { directionClass, figure } from "@/lib/format";
import { cn } from "@/lib/utils";

const STATUS_BADGE: Record<string, string> = {
  detected: "bg-slate-100 text-slate-700",
  investigating: "bg-accent-subtle text-accent",
  awaiting_controller: "bg-amber-100 text-amber-800",
  drafted: "bg-indigo-100 text-indigo-800",
  accepted: "bg-emerald-100 text-emerald-800",
  dismissed: "bg-slate-100 text-slate-400",
  failed: "bg-red-100 text-unfavorable",
};

const STATUS_LABEL: Record<string, string> = {
  detected: "Flagged",
  investigating: "Investigating…",
  awaiting_controller: "Awaiting you",
  drafted: "Drafted",
  accepted: "Accepted",
  dismissed: "Dismissed",
  failed: "Investigation failed",
};

export interface VarianceCardProps {
  variance: FlaggedVarianceView;
  item?: ReviewItemView | null;
  selected?: boolean;
  busy?: boolean;
  error?: string | null;
  onSelect?: () => void;
  onInvestigate?: () => void;
  onAnswer?: (text: string) => void;
  onAccept?: () => void;
  onEditAndAccept?: (text: string) => void;
  onDismiss?: () => void;
}

export function VarianceCard(props: VarianceCardProps) {
  const { variance, item, selected, busy, error } = props;
  const status: ReviewStatus | "detected" = busy ? "investigating" : (item?.status ?? "detected");
  const settled = status === "accepted" || status === "dismissed";

  const [answer, setAnswer] = useState("");
  const [editing, setEditing] = useState(false);
  const currentCommentary = item?.edited_text ?? item?.original_draft?.commentary ?? "";
  const [editText, setEditText] = useState(currentCommentary);

  return (
    <Card
      data-testid={`card-${variance.flag_id}`}
      data-status={status}
      data-selected={!!selected}
      onClick={props.onSelect}
      className={cn(
        "cursor-pointer transition-shadow",
        selected && "ring-2 ring-accent",
        settled && "opacity-70",
      )}
    >
      <CardHeader>
        <div>
          <div className="font-semibold">{variance.reporting_line}</div>
          <div className="text-xs text-slate-500">
            {variance.time_cut} · {variance.scenario_pair}
          </div>
        </div>
        <Badge className={STATUS_BADGE[status]}>{STATUS_LABEL[status]}</Badge>
      </CardHeader>

      <CardContent className="space-y-2">
        {/* Figures rendered verbatim from served display strings; direction colors only. */}
        <div className="num flex flex-wrap gap-x-4 gap-y-1 text-sm tabular-nums">
          <span>
            <span className="text-slate-500">Current </span>
            <span className={directionClass(variance.direction)}>{figure(variance.current_display)}</span>
          </span>
          <span>
            <span className="text-slate-500">vs </span>
            {figure(variance.comparator_display)}
          </span>
          {variance.abs_display && (
            <span className={directionClass(variance.direction)}>Δ {variance.abs_display}</span>
          )}
          {variance.pct_display && (
            <span className={directionClass(variance.direction)}>{variance.pct_display}</span>
          )}
          {variance.pp_display && (
            <span className={directionClass(variance.direction)}>{variance.pp_display}</span>
          )}
        </div>

        {error && <div className="text-sm text-unfavorable">⚠ {error}</div>}

        {status === "investigating" && (
          <div className="text-sm text-accent">Investigating the general ledger…</div>
        )}

        {status === "failed" && (
          <div className="text-sm text-unfavorable">⚠ {item?.error ?? "Investigation failed."}</div>
        )}

        {status === "awaiting_controller" && item?.record?.question && (
          <div className="space-y-2 rounded-md bg-amber-50 p-3">
            <p className="text-sm text-slate-800">{item.record.question.text}</p>
            {item.record.question.hypothesis?.text && (
              <p className="text-xs text-slate-500">Hypothesis: {item.record.question.hypothesis.text}</p>
            )}
            <Textarea
              aria-label="Your answer"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Add the context the agent needs…"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        )}

        {(status === "drafted" || status === "accepted") && (
          <div className="rounded-md bg-canvas p-3 text-sm text-slate-800">
            {editing ? (
              <Textarea
                aria-label="Edit commentary"
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <p>{currentCommentary}</p>
            )}
          </div>
        )}
      </CardContent>

      <CardFooter onClick={(e) => e.stopPropagation()}>
        {editing ? (
          <>
            <Button
              onClick={() => {
                // edit reverts to drafted server-side (retaining the original), then re-accept —
                // applied sequentially by the handler so the writes never race.
                props.onEditAndAccept?.(editText);
                setEditing(false);
              }}
            >
              Save &amp; accept
            </Button>
            <Button variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </>
        ) : (
          <>
            {status === "detected" && <Button onClick={props.onInvestigate}>Investigate</Button>}

            {status === "failed" && (
              <>
                <Button onClick={props.onInvestigate}>Retry</Button>
                <Button variant="danger" onClick={props.onDismiss}>
                  Dismiss
                </Button>
              </>
            )}

            {status === "awaiting_controller" && (
              <>
                <Button disabled={!answer.trim()} onClick={() => props.onAnswer?.(answer.trim())}>
                  Submit
                </Button>
                <Button variant="danger" onClick={props.onDismiss}>
                  Dismiss
                </Button>
              </>
            )}

            {status === "drafted" && (
              <>
                <Button onClick={props.onAccept}>Accept</Button>
                <Button variant="outline" onClick={() => setEditing(true)}>
                  Edit
                </Button>
                <Button variant="danger" onClick={props.onDismiss}>
                  Dismiss
                </Button>
              </>
            )}

            {status === "accepted" && (
              <>
                <Button variant="outline" onClick={() => setEditing(true)}>
                  Edit
                </Button>
                <Button variant="danger" onClick={props.onDismiss}>
                  Dismiss
                </Button>
              </>
            )}
          </>
        )}
      </CardFooter>
    </Card>
  );
}
