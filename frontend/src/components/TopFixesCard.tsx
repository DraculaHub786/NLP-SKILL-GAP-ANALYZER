import { motion } from "framer-motion";
import type { Finding } from "../types/resumeIntelligenceReport";

interface TopFixesCardProps {
  fixes: Finding[];
}

const SEVERITY_DOT: Record<string, string> = {
  critical: "bg-red-500",
  major: "bg-orange-500",
  minor: "bg-amber-500",
  info: "bg-gray-400",
};

export function TopFixesCard({ fixes }: TopFixesCardProps) {
  if (!fixes.length) return null;

  return (
    <section className="mb-10 rounded-2xl border-2 border-accent/40 bg-accent/5 p-5" aria-label="Top fixes">
      <h2 className="font-semibold mb-4">⚡ Top fixes to make now</h2>
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
              <p className="flex items-center gap-2 text-sm font-medium text-gray-800 dark:text-gray-100">
                <span className={`shrink-0 w-2 h-2 rounded-full ${SEVERITY_DOT[fix.severity] ?? "bg-gray-400"}`} />
                <span className="break-words">{fix.message}</span>
              </p>
              <p className="text-xs text-gray-500 mt-1">
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
