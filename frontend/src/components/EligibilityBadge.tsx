import { motion } from "framer-motion";
import type { EligibilityResult } from "../types/resumeIntelligenceReport";

interface EligibilityBadgeProps {
  eligibility: EligibilityResult;
}

const BAND_STYLES: Record<string, { bg: string; text: string; icon: string }> = {
  strong_fit: { bg: "bg-status-success/10", text: "text-status-success", icon: "✓" },
  good_fit: { bg: "bg-accent-subtle", text: "text-accent", icon: "→" },
  moderate_fit: { bg: "bg-status-minor/10", text: "text-status-minor", icon: "~" },
  weak_fit: { bg: "bg-status-critical/10", text: "text-status-critical", icon: "✗" },
};

export function EligibilityBadge({ eligibility }: EligibilityBadgeProps) {
  const styles = BAND_STYLES[eligibility.band] ?? BAND_STYLES.moderate_fit;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4 }}
      className="text-center mb-4"
    >
      <span
        className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl3 text-sm font-medium ${styles.bg} ${styles.text}`}
      >
        <span className="text-base">{styles.icon}</span>
        {eligibility.label}
      </span>
      <p className="text-xs text-ink-muted mt-2">
        Estimated screening-pass likelihood:{" "}
        <span className="font-semibold font-tabular-nums">{eligibility.probability_estimate}%</span>
      </p>
      {eligibility.downgraded_by_hard_gate && (
        <p className="text-xs text-status-minor mt-1">
          Score adjusted due to critical formatting/ATS issues.
        </p>
      )}
    </motion.div>
  );
}
