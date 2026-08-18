import { motion } from "framer-motion";

interface WarningsBannerProps {
  warnings: string[];
}

export function WarningsBanner({ warnings }: WarningsBannerProps) {
  if (!warnings.length) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-6 rounded-xl2 bg-status-info/10 border border-status-info/20 px-5 py-3"
      role="alert"
    >
      <p className="text-sm font-medium text-status-info mb-1">⚠ Heads up</p>
      <ul className="space-y-1">
        {warnings.map((w, i) => (
          <li key={i} className="text-xs text-ink-secondary dark:text-ink-onDark leading-relaxed">
            {w}
          </li>
        ))}
      </ul>
    </motion.div>
  );
}
