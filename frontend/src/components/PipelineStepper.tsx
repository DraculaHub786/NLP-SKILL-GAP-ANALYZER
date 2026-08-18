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
      <ol className="space-y-3">
        {order.map((stage, index) => {
          const isDone = errorIndex === -1 && index < activeIndex;
          const isActive = index === activeIndex && errorIndex === -1;
          const isError = index === errorIndex;

          return (
            <motion.li
              key={stage}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
              className={`flex items-center gap-3 p-3 rounded-2xl border ${
                isError
                  ? "border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-900/20"
                  : isActive
                    ? "border-accent bg-accent/5"
                    : "border-gray-200 dark:border-gray-700"
              }`}
            >
              <span
                className={`w-8 h-8 shrink-0 rounded-full flex items-center justify-center text-sm font-semibold ${
                  isDone
                    ? "bg-green-500 text-white"
                    : isError
                      ? "bg-red-500 text-white"
                      : isActive
                        ? "bg-accent text-white"
                        : "bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-300"
                }`}
              >
                {isError ? "!" : isDone ? "✓" : index + 1}
              </span>
              <div className="min-w-0">
                <p
                  className={`font-medium ${
                    isError
                      ? "text-red-700 dark:text-red-300"
                      : "text-gray-800 dark:text-gray-100"
                  }`}
                >
                  {STAGE_LABELS[stage]}
                </p>
                {isActive && !isError && (
                  <p className="text-xs text-gray-500 animate-pulse">Working…</p>
                )}
                {isError && errorMessage && (
                  <p className="text-xs text-red-600 dark:text-red-300 break-words">
                    {errorMessage}
                  </p>
                )}
              </div>
              {isActive && !isError && (
                <motion.span
                  className="ml-auto w-4 h-4 shrink-0 rounded-full border-2 border-accent border-t-transparent"
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 0.8, ease: "linear" }}
                />
              )}
              {isError && (
                <button
                  onClick={onRetry}
                  className="ml-auto shrink-0 px-3 py-1 rounded-full text-xs font-semibold bg-red-500 text-white hover:bg-red-600 transition"
                >
                  Retry
                </button>
              )}
            </motion.li>
          );
        })}
      </ol>
    </div>
  );
}
