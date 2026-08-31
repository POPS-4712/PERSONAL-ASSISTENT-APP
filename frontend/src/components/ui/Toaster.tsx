import { createPortal } from "react-dom";
import { useToast, type ToastKind } from "@/stores/toast";
import { cn } from "@/utils/cn";

const tone: Record<ToastKind, string> = {
  success: "border-ok/40 bg-ok/10",
  error: "border-danger/40 bg-danger/10",
  info: "border-info/40 bg-info/10",
  warning: "border-warn/40 bg-warn/10",
};

const dot: Record<ToastKind, string> = {
  success: "bg-ok",
  error: "bg-danger",
  info: "bg-info",
  warning: "bg-warn",
};

export function Toaster() {
  const { toasts, dismiss } = useToast();

  return createPortal(
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-full max-w-sm flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          className={cn(
            "pointer-events-auto flex items-start gap-3 rounded-xl border bg-surface p-3 shadow-lg",
            tone[t.kind],
          )}
        >
          <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", dot[t.kind])} />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-fg">{t.title}</p>
            {t.description && <p className="mt-0.5 break-words text-xs text-muted">{t.description}</p>}
          </div>
          <button
            onClick={() => dismiss(t.id)}
            className="text-muted hover:text-fg"
            aria-label="Dismiss notification"
          >
            ✕
          </button>
        </div>
      ))}
    </div>,
    document.body,
  );
}
