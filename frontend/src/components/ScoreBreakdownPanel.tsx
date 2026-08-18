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
  if (score >= 80) return "#2FAE6B";
  if (score >= 60) return "#FF7A29";
  if (score >= 40) return "#D9A93C";
  return "#E0473E";
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
        <p className="mt-2 text-ink-secondary text-sm">Overall Resume Score</p>
      </div>

      <div className={`grid gap-4 ${match ? "sm:grid-cols-3" : "sm:grid-cols-2"} max-w-2xl mx-auto`}>
        {subScores.map((sub, i) => (
          <motion.div
            key={sub.key}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.1 }}
            className="rounded-xl2 bg-surface-card dark:bg-surface-darkCard shadow-soft hover:shadow-liftHover transition-shadow p-5 text-center"
          >
            <p className="text-sm font-medium text-ink-secondary dark:text-ink-onDark">{sub.label}</p>
            <p className="text-3xl font-semibold font-tabular-nums mt-2" style={{ color: subScoreColor(sub.score) }}>
              {Math.round(sub.score)}
              <span className="text-base text-ink-muted">/100</span>
            </p>
            {/* Accent bar showing contribution */}
            <div className="mt-3 h-1.5 rounded-full bg-surface-sunken dark:bg-surface-dark overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ backgroundColor: subScoreColor(sub.score) }}
                initial={{ width: 0 }}
                animate={{ width: `${Math.min(100, sub.score)}%` }}
                transition={{ delay: 0.3 + i * 0.1, duration: 0.6, ease: "easeOut" }}
              />
            </div>
            <p className="text-xs text-ink-muted mt-2">{sub.detail}</p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
