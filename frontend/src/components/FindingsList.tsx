import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Finding, FindingCategory, FindingSeverity } from "../types/resumeIntelligenceReport";

interface FindingsListProps {
  findings: Finding[];
}

const CATEGORY_LABELS: Record<FindingCategory, string> = {
  ats: "ATS Compatibility",
  content: "Content Quality",
  match: "JD Match",
};

const SEVERITY_DOT: Record<FindingSeverity, string> = {
  critical: "bg-status-critical",
  major: "bg-status-major",
  minor: "bg-status-minor",
  info: "bg-ink-muted",
};

const SEVERITY_BORDER: Record<FindingSeverity, string> = {
  critical: "border-status-critical/30",
  major: "border-status-major/30",
  minor: "border-status-minor/30",
  info: "border-ink-muted/30",
};

const SEVERITY_ORDER: FindingSeverity[] = ["critical", "major", "minor", "info"];

export function FindingsList({ findings }: FindingsListProps) {
  const [activeCategory, setActiveCategory] = useState<FindingCategory | "all">("all");
  const [activeSeverity, setActiveSeverity] = useState<FindingSeverity | "all">("all");
  const [expanded, setExpanded] = useState<string | null>(null);

  const filtered = findings.filter(
    (f) =>
      (activeCategory === "all" || f.category === activeCategory) &&
      (activeSeverity === "all" || f.severity === activeSeverity)
  );
  const sorted = [...filtered].sort(
    (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)
  );

  const categories = ["all", "ats", "content", "match"] as const;
  const severities = ["all", "critical", "major", "minor", "info"] as const;

  return (
    <section className="mb-10" aria-label="Detailed findings">
      <h2 className="text-lg font-semibold tracking-tight mb-3">📋 Detailed findings</h2>

      <div className="flex flex-wrap gap-2 mb-4">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            className={`px-3 py-1.5 rounded-xl2 text-sm font-medium transition active:scale-[0.98] ${
              activeCategory === cat
                ? "bg-accent text-white shadow-soft"
                : "bg-surface-card dark:bg-surface-darkCard text-ink-secondary dark:text-ink-onDark border border-surface-sunken dark:border-surface-darkCard hover:shadow-soft"
            }`}
          >
            {cat === "all" ? "All" : CATEGORY_LABELS[cat as FindingCategory]}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2 mb-5">
        {severities.map((sev) => (
          <button
            key={sev}
            onClick={() => setActiveSeverity(sev)}
            className={`px-3 py-1.5 rounded-xl2 text-xs font-medium transition active:scale-[0.98] ${
              activeSeverity === sev
                ? "bg-ink-primary dark:bg-ink-onDark text-white dark:text-ink-primary shadow-soft"
                : "bg-surface-card dark:bg-surface-darkCard text-ink-secondary dark:text-ink-onDark border border-surface-sunken dark:border-surface-darkCard hover:shadow-soft"
            }`}
          >
            {sev === "all" ? "All severities" : sev}
          </button>
        ))}
      </div>

      {sorted.length === 0 ? (
        <p className="text-sm text-ink-muted">No findings match the current filters.</p>
      ) : (
        <ul className="space-y-3" data-testid="findings-list">
          {sorted.map((finding, i) => {
            const key = `${finding.category}-${i}-${finding.message.slice(0, 20)}`;
            const isExpanded = expanded === key;
            const dotColor = SEVERITY_DOT[finding.severity];
            const borderColor = SEVERITY_BORDER[finding.severity];

            return (
              <li key={key}>
                <button
                  onClick={() => setExpanded(isExpanded ? null : key)}
                  className={`w-full text-left rounded-xl2 bg-surface-card dark:bg-surface-darkCard shadow-soft hover:shadow-liftHover transition-shadow border ${borderColor} p-4`}
                  aria-expanded={isExpanded}
                >
                  <div className="flex items-start gap-3">
                    <span className={`shrink-0 w-2.5 h-2.5 rounded-full mt-1.5 ${dotColor}`} />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-ink-primary dark:text-ink-onDark">
                        {finding.message}
                      </p>
                      <p className="text-xs text-ink-muted mt-1">
                        {CATEGORY_LABELS[finding.category]}
                        {finding.section ? ` · ${finding.section}` : ""}
                      </p>
                    </div>
                    <span className="shrink-0 text-ink-muted text-lg">{isExpanded ? "−" : "+"}</span>
                  </div>

                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="mt-3 pt-3 border-t border-surface-sunken dark:border-surface-dark space-y-2 text-sm">
                          <p className="text-ink-secondary dark:text-ink-onDark">{finding.why_it_matters}</p>
                          <p className="text-ink-primary dark:text-ink-onDark">
                            <span className="font-medium">Fix: </span>
                            {finding.fix_suggestion}
                          </p>
                          {finding.example_before && (
                            <div className="rounded-xl bg-status-critical/5 p-3 border border-status-critical/10">
                              <p className="text-xs font-medium text-status-critical mb-1">Before</p>
                              <p className="text-xs text-ink-secondary dark:text-ink-onDark whitespace-pre-wrap">{finding.example_before}</p>
                            </div>
                          )}
                          {finding.example_after && (
                            <div className="rounded-xl bg-status-success/5 p-3 border border-status-success/10">
                              <p className="text-xs font-medium text-status-success mb-1">After</p>
                              <p className="text-xs text-ink-secondary dark:text-ink-onDark whitespace-pre-wrap">{finding.example_after}</p>
                            </div>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
