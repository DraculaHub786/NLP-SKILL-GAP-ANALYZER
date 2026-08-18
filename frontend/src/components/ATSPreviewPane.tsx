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
      className="mb-10 rounded-2xl border border-gray-200 dark:border-gray-700 overflow-hidden"
      aria-label="What the parser sees"
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/60">
        <p className="text-sm font-medium">🔍 What the parser sees</p>
        <p className="text-xs text-gray-500">Plain extracted text — no formatting</p>
      </div>
      <pre className="text-xs leading-relaxed whitespace-pre-wrap break-words p-4 text-gray-700 dark:text-gray-300 font-mono max-h-72 overflow-y-auto bg-white dark:bg-[#1e1e1e]">
        {rawText.trim()}
      </pre>
    </motion.section>
  );
}
