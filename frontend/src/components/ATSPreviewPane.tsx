import { motion } from "framer-motion";

interface ATSPreviewPaneProps {
  rawText?: string;
}

export function ATSPreviewPane({ rawText }: ATSPreviewPaneProps) {
  if (!rawText || !rawText.trim()) return null;

  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-10 rounded-xl2 bg-surface-card dark:bg-surface-darkCard shadow-soft overflow-hidden"
      aria-label="What the parser sees"
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-sunken dark:border-surface-dark">
        <p className="text-sm font-medium text-ink-primary dark:text-ink-onDark">🔍 What the parser sees</p>
        <p className="text-xs text-ink-muted">Plain extracted text — no formatting</p>
      </div>
      <pre className="text-xs leading-relaxed whitespace-pre-wrap break-words p-4 text-ink-secondary dark:text-ink-onDark font-mono max-h-72 overflow-y-auto bg-surface-sunken/50 dark:bg-surface-dark">
        {rawText.trim()}
      </pre>
    </motion.section>
  );
}
