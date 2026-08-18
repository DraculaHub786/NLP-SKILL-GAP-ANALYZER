import { motion } from "framer-motion";
import type { Finding } from "../types/resumeIntelligenceReport";

interface TopFixesCardProps {
  fixes: Finding[];
}

const SEVERITY_DOT: Record<string, string> = {
  critical: "bg-status-critical",
  major: "bg-status-major",
  minor: "bg-status-minor",
  info: "bg-ink-muted",
};

export function TopFixesCard({ fixes }: TopFixesCardProps) {
  if (!fixes.length) return null;

  return (
    <section className="mb-10 rounded-xl2 border-2 border-accent/30 bg-accent-subtle/30 dark:bg-accent/5 p-5 shadow-soft" aria-label="Top fixes">
      <h2 className="text-lg font-semibold tracking-tight mb-4">⚡ Top fixes to make now</h2>
      <ol className="space-y-3">
        {fixes.map((fix, i) => (
          <motion.li
            key={`${fix.category}-${i}-${fix.message.slice(0, 16)}`}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08 }}
            className="flex items-start gap-3"
          >
            <span className="shrink-0 w-6 h-6 rounded-full bg-accent text-white text-xs flex items-center justify-center font-semibold mt-0.5">
              {i + 1}
            </span>
            <div className="min-w-0">
              <p className="flex items-center gap-2 text-sm font-medium text-ink-primary dark:text-ink-onDark">
                <span className={`shrink-0 w-2 h-2 rounded-full ${SEVERITY_DOT[fix.severity] ?? "bg-ink-muted"}`} />
                <span className="break-words">{fix.message}</span>
              </p>
              <p className="text-xs text-ink-muted mt-1">
                {fix.fix_suggestion}
                {fix.section ? ` (${fix.section})` : ""}
              </p>
            </div>
          </motion.li>
        ))}
      </ol>
    </section>
  );
}
