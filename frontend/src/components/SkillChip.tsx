import { motion } from "framer-motion";

type Variant = "matched" | "missing" | "bonus";

const styles: Record<Variant, string> = {
  matched: "bg-status-success/10 text-status-success border border-status-success/20",
  missing: "bg-status-critical/10 text-status-critical border border-status-critical/20",
  bonus: "bg-accent-subtle text-accent border border-accent-subtle",
};

const icons: Record<Variant, string> = {
  matched: "✓",
  missing: "✗",
  bonus: "+",
};

export function SkillChip({ label, variant, index = 0 }: { label: string; variant: Variant; index?: number }) {
  return (
    <motion.span
      initial={{ opacity: 0, y: 8, scale: 0.9 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: index * 0.04, type: "spring", stiffness: 300, damping: 20 }}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium mr-2 mb-2 ${styles[variant]}`}
    >
      <span className="text-xs" aria-hidden="true">{icons[variant]}</span>
      {label}
    </motion.span>
  );
}
