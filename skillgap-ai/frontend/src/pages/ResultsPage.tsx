import { motion } from "framer-motion";
import { ScoreRing } from "../components/ScoreRing";
import { SkillChip } from "../components/SkillChip";
import type { GapReport } from "../types/gapReport";

interface ResultsPageProps {
  report: GapReport;
  onReset: () => void;
}

export function ResultsPage({ report, onReset }: ResultsPageProps) {
  return (
    <div className="min-h-screen bg-white dark:bg-[#121212] text-gray-800 dark:text-gray-100 px-6 py-10 transition-colors">
      <div className="max-w-3xl mx-auto">
        <div className="flex justify-between items-start mb-6">
          <button
            onClick={onReset}
            className="px-3 py-1.5 rounded-full text-sm border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
          >
            ← New analysis
          </button>
        </div>

        <div className="flex flex-col items-center mb-10">
          <ScoreRing score={report.match_score} />
          <p className="mt-2 text-gray-500">Overall match with this role</p>
          {report.summary && (
            <p className="mt-3 text-sm text-center text-gray-600 dark:text-gray-300 max-w-md">
              {report.summary}
            </p>
          )}
        </div>

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

        <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}>
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
      </div>
    </div>
  );
}
