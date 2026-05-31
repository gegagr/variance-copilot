import type { FlaggedVarianceView, ReviewItemView } from "@/api/schema";
import { VarianceCard } from "@/components/VarianceCard";
import { cn } from "@/lib/utils";

export interface PanelHandlers {
  onInvestigate: (flagId: string) => void;
  onAnswer: (flagId: string, text: string) => void;
  onAccept: (flagId: string) => void;
  onEditAndAccept: (flagId: string, text: string) => void;
  onDismiss: (flagId: string) => void;
}

export function VarianceReviewPanel({
  variances,
  itemByFlag,
  selectedFlagId,
  selectedLine,
  onSelect,
  pending,
  errors,
  handlers,
}: {
  variances: FlaggedVarianceView[];
  itemByFlag: Map<string, ReviewItemView>;
  selectedFlagId: string | null;
  selectedLine: string | null;
  onSelect: (flagId: string) => void;
  pending: Record<string, boolean>;
  errors: Record<string, string | null>;
  handlers: PanelHandlers;
}) {
  if (variances.length === 0) {
    return <div className="rounded-lg border border-dashed border-border p-8 text-center text-slate-500">No flagged variances 🎉</div>;
  }
  return (
    <div className="flex flex-col gap-3">
      {variances.map((v) => (
        <div
          key={v.flag_id}
          className={cn(selectedLine === v.reporting_line && "rounded-lg ring-1 ring-accent/40")}
        >
          <VarianceCard
            variance={v}
            item={itemByFlag.get(v.flag_id) ?? null}
            selected={selectedFlagId === v.flag_id}
            busy={pending[v.flag_id]}
            error={errors[v.flag_id] ?? null}
            onSelect={() => onSelect(v.flag_id)}
            onInvestigate={() => handlers.onInvestigate(v.flag_id)}
            onAnswer={(text) => handlers.onAnswer(v.flag_id, text)}
            onAccept={() => handlers.onAccept(v.flag_id)}
            onEditAndAccept={(text) => handlers.onEditAndAccept(v.flag_id, text)}
            onDismiss={() => handlers.onDismiss(v.flag_id)}
          />
        </div>
      ))}
    </div>
  );
}
