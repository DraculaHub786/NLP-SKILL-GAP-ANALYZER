import { motion } from "framer-motion";
import { ScoreRing } from "../components/ScoreRing";
import { SkillChip } from "../components/SkillChip";

interface GapReport {
  match_score: number;
  matched: { resume_skill: string; jd_skill: string; similarity: number }[];
  missing: string[];
  bonus: string[];
  recommendations: { skill: string; importance: number; resources: string[] }[];
}

export function ResultsPage({ report }: { report: GapReport }) {
  return (
    <div className="min-h-screen bg-white dark:bg-[#121212] text-gray-800 dark:text-gray-100 px-6 py-10 transition-colors">
      <div className="max-w-3xl mx-auto">
        <div className="flex flex-col items-center mb-10">
          <ScoreRing score={report.match_score} />
          <p className="mt-2 text-gray-500">Overall match with this role</p>
        </div>

        <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }} className="mb-8">
          <h2 className="font-semibold mb-3">✅ Matched skills</h2>
          {report.matched.map((m, i) => (
            <SkillChip key={m.jd_skill} label={m.jd_skill} variant="matched" index={i} />
          ))}
        </motion.section>

        <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="mb-8">
          <h2 className="font-semibold mb-3">⚠️ Missing skills</h2>
          {report.missing.map((s, i) => (
            <SkillChip key={s} label={s} variant="missing" index={i} />
          ))}
        </motion.section>

        <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }} className="mb-8">
          <h2 className="font-semibold mb-3">⭐ Bonus skills</h2>
          {report.bonus.map((s, i) => (
            <SkillChip key={s} label={s} variant="bonus" index={i} />
          ))}
        </motion.section>

        <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}>
          <h2 className="font-semibold mb-3">📚 Recommended next steps</h2>
          <div className="space-y-3">
            {report.recommendations.map((r) => (
              <div key={r.skill} className="p-4 rounded-2xl border border-gray-200 dark:border-gray-700">
                <p className="font-medium">{r.skill}</p>
                <a href={r.resources[0]} target="_blank" rel="noreferrer" className="text-sm text-accent">
                  Start learning →
                </a>
              </div>
            ))}
          </div>
        </motion.section>
      </div>
    </div>
  );
}
