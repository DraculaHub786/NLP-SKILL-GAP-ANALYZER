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

const SEVERITY_STYLES: Record<FindingSeverity, { badge: string; border: string }> = {
  critical: { badge: "bg-red-500 text-white", border: "border-red-300 dark:border-red-800" },
  major: { badge: "bg-orange-500 text-white", border: "border-orange-300 dark:border-orange-800" },
  minor: { badge: "bg-amber-500 text-white", border: "border-amber-300 dark:border-amber-800" },
  info: { badge: "bg-gray-400 text-white", border: "border-gray-300 dark:border-gray-700" },
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
      <h2 className="font-semibold mb-3">📋 Detailed findings</h2>

      <div className="flex flex-wrap gap-2 mb-4">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            className={`px-3 py-1 rounded-full text-sm border transition ${
              activeCategory === cat
                ? "bg-accent text-white border-accent"
                : "border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800"
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
            className={`px-3 py-1 rounded-full text-xs border transition ${
              activeSeverity === sev
                ? "bg-gray-800 text-white dark:bg-gray-100 dark:text-gray-900 border-gray-800 dark:border-gray-100"
                : "border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800"
            }`}
          >
            {sev === "all" ? "All severities" : sev}
          </button>
        ))}
      </div>

      {sorted.length === 0 ? (
        <p className="text-sm text-gray-500">No findings match the current filters.</p>
      ) : (
        <ul className="space-y-3" data-testid="findings-list">
          {sorted.map((finding, i) => {
            const key = `${finding.category}-${i}-${finding.message.slice(0, 20)}`;
            const isExpanded = expanded === key;
            const styles = SEVERITY_STYLES[finding.severity];

            return (
              <li key={key}>
                <button
                  onClick={() => setExpanded(isExpanded ? null : key)}
                  className={`w-full text-left rounded-2xl border p-4 transition ${styles.border} hover:bg-gray-50 dark:hover:bg-gray-900/40`}
                  aria-expanded={isExpanded}
                >
                  <div className="flex items-start gap-3">
                    <span className={`shrink-0 px-2 py-0.5 rounded-full text-xs font-semibold ${styles.badge}`}>
                      {finding.severity}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-800 dark:text-gray-100">
                        {finding.message}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        {CATEGORY_LABELS[finding.category]}
                        {finding.section ? ` · ${finding.section}` : ""}
                      </p>
                    </div>
                    <span className="shrink-0 text-gray-400">{isExpanded ? "−" : "+"}</span>
                  </div>

                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800 space-y-2 text-sm">
                          <p className="text-gray-600 dark:text-gray-300">{finding.why_it_matters}</p>
                          <p className="text-gray-800 dark:text-gray-100">
                            <span className="font-medium">Fix: </span>
                            {finding.fix_suggestion}
                          </p>
                          {finding.example_before && (
                            <div className="rounded-lg bg-red-50 dark:bg-red-900/20 p-3 border border-red-100 dark:border-red-900/40">
                              <p className="text-xs font-medium text-red-600 dark:text-red-400 mb-1">Before</p>
                              <p className="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{finding.example_before}</p>
                            </div>
                          )}
                          {finding.example_after && (
                            <div className="rounded-lg bg-green-50 dark:bg-green-900/20 p-3 border border-green-100 dark:border-green-900/40">
                              <p className="text-xs font-medium text-green-600 dark:text-green-400 mb-1">After</p>
                              <p className="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{finding.example_after}</p>
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
