import { motion } from "framer-motion";

export type PipelineStage = "resume" | "jd" | "gap";

const STAGE_LABELS: Record<PipelineStage, string> = {
  resume: "Parsing resume",
  jd: "Extracting JD skills",
  gap: "Computing gap",
};

interface PipelineStepperProps {
  activeStage: PipelineStage;
  errorStage: PipelineStage | null;
  errorMessage: string | null;
  onRetry: () => void;
}

export function PipelineStepper({
  activeStage,
  errorStage,
  errorMessage,
  onRetry,
}: PipelineStepperProps) {
  const order: PipelineStage[] = ["resume", "jd", "gap"];
  const activeIndex = order.indexOf(activeStage);
  const errorIndex = errorStage ? order.indexOf(errorStage) : -1;

  return (
    <div className="w-full max-w-md" role="status" aria-live="polite">
      {/* Horizontal progress track */}
      <div className="flex items-center justify-between mb-8">
        {order.map((stage, index) => {
          const isDone = errorIndex === -1 && index < activeIndex;
          const isActive = index === activeIndex && errorIndex === -1;
          const isError = index === errorIndex;

          return (
            <div key={stage} className="flex items-center flex-1 last:flex-none">
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: index * 0.1 }}
                className={`relative w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold transition-colors ${
                  isDone
                    ? "bg-status-success text-white"
                    : isError
                      ? "bg-status-critical text-white"
                      : isActive
                        ? "bg-accent text-white"
                        : "bg-surface-sunken dark:bg-surface-darkCard text-ink-muted"
                }`}
              >
                {isError ? "!" : isDone ? "✓" : index + 1}
                {isActive && !isError && (
                  <motion.span
                    className="absolute inset-0 rounded-full border-2 border-accent border-t-transparent"
                    animate={{ rotate: 360 }}
                    transition={{ repeat: Infinity, duration: 0.8, ease: "linear" }}
                  />
                )}
              </motion.div>
              {/* Connecting line */}
              {index < order.length - 1 && (
                <div className="flex-1 h-0.5 mx-2 rounded-full bg-surface-sunken dark:bg-surface-darkCard overflow-hidden">
                  <motion.div
                    className="h-full bg-status-success rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: isDone ? "100%" : "0%" }}
                    transition={{ duration: 0.4, ease: "easeOut" }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Status label */}
      <div className="text-center">
        <ol className="space-y-3">
          {order.map((stage, index) => {
            const isDone = errorIndex === -1 && index < activeIndex;
            const isActive = index === activeIndex && errorIndex === -1;
            const isError = index === errorIndex;

            return (
              <motion.li
                key={stage}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                className={`flex items-center justify-between p-3 rounded-xl2 border transition-colors ${
                  isError
                    ? "border-status-critical/30 bg-status-critical/5"
                    : isActive
                      ? "border-accent/30 bg-accent-subtle/20 dark:bg-accent/5"
                      : isDone
                        ? "border-status-success/20 bg-status-success/5"
                        : "border-surface-sunken dark:border-surface-darkCard"
                }`}
              >
                <div className="min-w-0">
                  <p
                    className={`text-sm font-medium ${
                      isError
                        ? "text-status-critical"
                        : isActive
                          ? "text-ink-primary dark:text-ink-onDark"
                          : isDone
                            ? "text-status-success"
                            : "text-ink-muted"
                    }`}
                  >
                    {STAGE_LABELS[stage]}
                  </p>
                  {isActive && !isError && (
                    <p className="text-xs text-ink-muted animate-pulse">Working…</p>
                  )}
                  {isError && errorMessage && (
                    <p className="text-xs text-status-critical break-words mt-0.5">
                      {errorMessage}
                    </p>
                  )}
                </div>
                {isError && (
                  <button
                    onClick={onRetry}
                    className="shrink-0 px-3 py-1.5 rounded-xl2 text-xs font-semibold bg-status-critical text-white hover:bg-status-critical/80 transition active:scale-[0.98]"
                  >
                    Retry
                  </button>
                )}
              </motion.li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
