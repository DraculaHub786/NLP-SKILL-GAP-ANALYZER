import { useEffect, useState } from "react";
import { motion } from "framer-motion";

function scoreColor(score: number): string {
  if (score >= 80) return "#2FAE6B";
  if (score >= 60) return "#FF7A29";
  if (score >= 40) return "#D9A93C";
  return "#E0473E";
}

export function ScoreRing({ score }: { score: number }) {
  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.min(100, Math.max(0, score));
  const offset = circumference - (clamped / 100) * circumference;

  const [displayScore, setDisplayScore] = useState(0);

  useEffect(() => {
    const duration = 800;
    const start = performance.now();
    const animate = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayScore(Math.round(eased * clamped));
      if (progress < 1) requestAnimationFrame(animate);
    };
    requestAnimationFrame(animate);
  }, [clamped]);

  return (
    <div className="relative w-44 h-44 flex items-center justify-center">
      <svg className="-rotate-90" width="176" height="176">
        <circle
          cx="88"
          cy="88"
          r={radius}
          stroke="currentColor"
          strokeWidth="10"
          fill="none"
          className="text-surface-sunken dark:text-surface-darkCard"
        />
        <motion.circle
          cx="88"
          cy="88"
          r={radius}
          stroke={scoreColor(clamped)}
          strokeWidth="10"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </svg>
      <motion.span
        className="absolute text-3xl font-semibold font-tabular-nums text-ink-primary dark:text-ink-onDark"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
      >
        {displayScore}%
      </motion.span>
    </div>
  );
}
