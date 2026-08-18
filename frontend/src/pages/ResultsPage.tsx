import { motion } from "framer-motion";
import { ATSPreviewPane } from "../components/ATSPreviewPane";
import { EligibilityBadge } from "../components/EligibilityBadge";
import { FindingsList } from "../components/FindingsList";
import { ScoreBreakdownPanel } from "../components/ScoreBreakdownPanel";
import { SectionHealthMap } from "../components/SectionHealthMap";
import { SkillChip } from "../components/SkillChip";
import { TopFixesCard } from "../components/TopFixesCard";
import { WarningsBanner } from "../components/WarningsBanner";
import type { ResumeIntelligenceReport } from "../types/resumeIntelligenceReport";

interface ResultsPageProps {
  report: ResumeIntelligenceReport;
  onReset: () => void;
}

export function ResultsPage({ report, onReset }: ResultsPageProps) {
  return (
    <div className="min-h-screen bg-surface-canvas dark:bg-surface-dark text-ink-primary dark:text-ink-onDark px-6 py-10 transition-colors">
      <div className="max-w-3xl mx-auto">
        <div className="flex justify-between items-start mb-8">
          <button
            onClick={onReset}
            className="px-3 py-1.5 rounded-xl2 text-sm border border-surface-sunken dark:border-surface-darkCard hover:bg-surface-sunken dark:hover:bg-surface-darkCard transition active:scale-[0.98]"
          >
            ← New analysis
          </button>
          <span className="text-xs text-ink-muted">
            {report.metadata?.no_jd_mode ? "ATS + Content only (no JD)" : "ATS + Content + JD Match"}
          </span>
        </div>

        {/* Warnings banner — visible when engines ran in degraded mode */}
        <WarningsBanner warnings={report.warnings} />

        {report.summary && (
          <p className="text-sm text-center text-ink-secondary dark:text-ink-onDark max-w-md mx-auto mb-6">
            {report.summary}
          </p>
        )}

        {/* Eligibility band — prominently above the score ring */}
        {report.eligibility && (
          <EligibilityBadge eligibility={report.eligibility} />
        )}

        <ScoreBreakdownPanel
          overall={report.overall_score}
          ats={report.ats_score}
          content={report.content_score}
          match={report.match_score}
        />

        <TopFixesCard fixes={report.top_fixes} />

        <SectionHealthMap sectionSummary={report.section_summary} />

        <ATSPreviewPane rawText={report.raw_text} />

        {report.match_score && (
          <>
            <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }} className="mb-8">
              <h2 className="text-lg font-semibold tracking-tight mb-3">✅ Matched skills</h2>
              {report.matched.length > 0 ? (
                report.matched.map((m, i) => (
                  <SkillChip key={m.jd_skill} label={m.jd_skill} variant="matched" index={i} />
                ))
              ) : (
                <p className="text-sm text-ink-muted">No matched skills found.</p>
              )}
            </motion.section>

            <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="mb-8">
              <h2 className="text-lg font-semibold tracking-tight mb-3">⚠️ Missing skills</h2>
              {report.missing.length > 0 ? (
                report.missing.map((s, i) => (
                  <SkillChip key={s} label={s} variant="missing" index={i} />
                ))
              ) : (
                <p className="text-sm text-ink-muted">Nothing missing — you have it all!</p>
              )}
            </motion.section>

            <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }} className="mb-8">
              <h2 className="text-lg font-semibold tracking-tight mb-3">⭐ Bonus skills</h2>
              {report.bonus.length > 0 ? (
                report.bonus.map((s, i) => (
                  <SkillChip key={s} label={s} variant="bonus" index={i} />
                ))
              ) : (
                <p className="text-sm text-ink-muted">No bonus skills beyond the role.</p>
              )}
            </motion.section>

            <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }} className="mb-8">
              <h2 className="text-lg font-semibold tracking-tight mb-3">📚 Recommended next steps</h2>
              {report.recommendations.length > 0 ? (
                <div className="space-y-3">
                  {report.recommendations.map((r) => (
                    <div key={r.skill} className="p-4 rounded-xl2 bg-surface-card dark:bg-surface-darkCard shadow-soft border border-surface-sunken dark:border-surface-darkCard">
                      <div className="flex items-center justify-between mb-1">
                        <p className="font-medium text-ink-primary dark:text-ink-onDark">{r.skill}</p>
                        {r.estimated_score_impact && (
                          <span className="text-xs font-medium text-accent bg-accent-subtle dark:bg-accent/10 px-2 py-0.5 rounded-full">
                            {r.estimated_score_impact}
                          </span>
                        )}
                      </div>
                      {r.resources[0] && (
                        <a href={r.resources[0]} target="_blank" rel="noreferrer" className="text-sm text-accent hover:text-accent-hover transition">
                          Start learning →
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-ink-muted">No recommendations — you're ready for this role.</p>
              )}
            </motion.section>
          </>
        )}

        <FindingsList findings={report.findings} />
      </div>
    </div>
  );
}
