import { motion } from "framer-motion";

type Variant = "matched" | "missing" | "bonus";

const styles: Record<Variant, string> = {
  matched: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  missing: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  bonus: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300",
};

export function SkillChip({ label, variant, index = 0 }: { label: string; variant: Variant; index?: number }) {
  return (
    <motion.span
      initial={{ opacity: 0, y: 8, scale: 0.9 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: index * 0.04, type: "spring", stiffness: 300, damping: 20 }}
      className={`inline-block px-3 py-1.5 rounded-full text-sm font-medium mr-2 mb-2 ${styles[variant]}`}
    >
      {label}
    </motion.span>
  );
}
