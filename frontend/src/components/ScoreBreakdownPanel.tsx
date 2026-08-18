import { motion } from "framer-motion";
import type { AtScore, ContentScore, MatchScore } from "../types/resumeIntelligenceReport";
import { ScoreRing } from "./ScoreRing";

interface ScoreBreakdownPanelProps {
  overall: number;
  ats: AtScore;
  content: ContentScore;
  match: MatchScore | null;
}

function subScoreColor(score: number): string {
  if (score >= 80) return "#1E8E3E"; // success green
  if (score >= 60) return "#F9AB00"; // warning amber
  return "#D93025"; // danger red
}

export function ScoreBreakdownPanel({ overall, ats, content, match }: ScoreBreakdownPanelProps) {
  const subScores = [
    {
      key: "ats",
      label: "ATS Compatibility",
      score: ats.score,
      detail: `${ats.findings.length} issue${ats.findings.length === 1 ? "" : "s"} found`,
    },
    {
      key: "content",
      label: "Content Quality",
      score: content.score,
      detail: `${content.quantified_bullet_pct}% bullets quantified`,
    },
    ...(match
      ? [
          {
            key: "match",
            label: "JD Match",
            score: match.score,
            detail: `${match.matched_count} matched · ${match.missing_count} missing`,
          },
        ]
      : []),
  ];

  return (
    <section className="mb-10" aria-label="Score breakdown">
      <div className="flex flex-col items-center mb-8">
        <ScoreRing score={overall} />
        <p className="mt-2 text-gray-500">Overall Resume Score</p>
      </div>

      <div className={`grid gap-4 ${match ? "sm:grid-cols-3" : "sm:grid-cols-2"} max-w-2xl mx-auto`}>
        {subScores.map((sub, i) => (
          <motion.div
            key={sub.key}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.1 }}
            className="rounded-2xl border border-gray-200 dark:border-gray-700 p-5 text-center"
          >
            <p className="text-sm font-medium text-gray-600 dark:text-gray-300">{sub.label}</p>
            <p className="text-3xl font-semibold mt-2" style={{ color: subScoreColor(sub.score) }}>
              {Math.round(sub.score)}
              <span className="text-base text-gray-400">/100</span>
            </p>
            <p className="text-xs text-gray-500 mt-2">{sub.detail}</p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
