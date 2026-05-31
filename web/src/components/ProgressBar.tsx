import { Progress } from "@/components/ui/progress";

export function ProgressBar({ resolved, total }: { resolved: number; total: number }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-slate-600">Review progress</span>
      <Progress value={resolved} max={total} className="w-40" />
      <span className="num text-sm font-medium text-slate-900">
        {resolved} / {total} resolved
      </span>
    </div>
  );
}
