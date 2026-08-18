import { motion } from "framer-motion";
import { ATSPreviewPane } from "../components/ATSPreviewPane";
import { FindingsList } from "../components/FindingsList";
import { ScoreBreakdownPanel } from "../components/ScoreBreakdownPanel";
import { SectionHealthMap } from "../components/SectionHealthMap";
import { SkillChip } from "../components/SkillChip";
import { TopFixesCard } from "../components/TopFixesCard";
import type { ResumeIntelligenceReport } from "../types/resumeIntelligenceReport";

interface ResultsPageProps {
  report: ResumeIntelligenceReport;
  onReset: () => void;
}

export function ResultsPage({ report, onReset }: ResultsPageProps) {
  return (
    <div className="min-h-screen bg-white dark:bg-[#121212] text-gray-800 dark:text-gray-100 px-6 py-10 transition-colors">
      <div className="max-w-3xl mx-auto">
        <div className="flex justify-between items-start mb-8">
          <button
            onClick={onReset}
            className="px-3 py-1.5 rounded-full text-sm border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
          >
            ← New analysis
          </button>
          <span className="text-xs text-gray-500">
            {report.metadata?.no_jd_mode ? "ATS + Content only (no JD)" : "ATS + Content + JD Match"}
          </span>
        </div>

        {report.summary && (
          <p className="text-sm text-center text-gray-600 dark:text-gray-300 max-w-md mx-auto mb-6">
            {report.summary}
          </p>
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
              <h2 className="font-semibold mb-3">✅ Matched skills</h2>
              {report.matched.length > 0 ? (
                report.matched.map((m, i) => (
                  <SkillChip key={m.jd_skill} label={m.jd_skill} variant="matched" index={i} />
                ))
              ) : (
                <p className="text-sm text-gray-500">No matched skills found.</p>
              )}
            </motion.section>

            <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="mb-8">
              <h2 className="font-semibold mb-3">⚠️ Missing skills</h2>
              {report.missing.length > 0 ? (
                report.missing.map((s, i) => (
                  <SkillChip key={s} label={s} variant="missing" index={i} />
                ))
              ) : (
                <p className="text-sm text-gray-500">Nothing missing — you have it all!</p>
              )}
            </motion.section>

            <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }} className="mb-8">
              <h2 className="font-semibold mb-3">⭐ Bonus skills</h2>
              {report.bonus.length > 0 ? (
                report.bonus.map((s, i) => (
                  <SkillChip key={s} label={s} variant="bonus" index={i} />
                ))
              ) : (
                <p className="text-sm text-gray-500">No bonus skills beyond the role.</p>
              )}
            </motion.section>

            <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }} className="mb-8">
              <h2 className="font-semibold mb-3">📚 Recommended next steps</h2>
              {report.recommendations.length > 0 ? (
                <div className="space-y-3">
                  {report.recommendations.map((r) => (
                    <div key={r.skill} className="p-4 rounded-2xl border border-gray-200 dark:border-gray-700">
                      <p className="font-medium">{r.skill}</p>
                      {r.resources[0] && (
                        <a href={r.resources[0]} target="_blank" rel="noreferrer" className="text-sm text-accent">
                          Start learning →
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500">No recommendations — you're ready for this role.</p>
              )}
            </motion.section>
          </>
        )}

        <FindingsList findings={report.findings} />
      </div>
    </div>
  );
}
