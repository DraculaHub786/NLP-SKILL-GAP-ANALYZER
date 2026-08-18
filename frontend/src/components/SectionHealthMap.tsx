import { motion } from "framer-motion";

interface SectionHealthMapProps {
  sectionSummary: Record<string, string>;
}

const SECTION_LABELS: Record<string, string> = {
  contact: "Contact Info",
  summary: "Summary / Objective",
  skills: "Skills",
  experience: "Experience",
  education: "Education",
  certifications: "Certifications",
};

function statusConfig(status: string | undefined) {
  if (status === "present") {
    return { dot: "bg-green-500", label: "Present", icon: "✓" };
  }
  if (status === "missing") {
    return { dot: "bg-red-500", label: "Missing", icon: "✗" };
  }
  return { dot: "bg-gray-300 dark:bg-gray-600", label: "Not detected", icon: "?" };
}

export function SectionHealthMap({ sectionSummary }: SectionHealthMapProps) {
  const sections = Object.keys(SECTION_LABELS);
  const presentCount = sections.filter((s) => sectionSummary[s] === "present").length;

  return (
    <section className="mb-10" aria-label="Section health">
      <h2 className="font-semibold mb-2">📑 Required sections</h2>
      <p className="text-xs text-gray-500 mb-4">
        {presentCount} of {sections.length} present
      </p>
      <ul className="grid sm:grid-cols-2 gap-2">
        {sections.map((key, i) => {
          const status = sectionSummary[key];
          const config = statusConfig(status);
          return (
            <motion.li
              key={key}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-center gap-3 rounded-xl border border-gray-200 dark:border-gray-700 px-3 py-2"
            >
              <span className={`shrink-0 w-2 h-2 rounded-full ${config.dot}`} />
              <span className="text-sm flex-1">{SECTION_LABELS[key]}</span>
              <span
                className={`text-xs font-medium ${
                  config.dot.includes("green")
                    ? "text-green-600 dark:text-green-400"
                    : config.dot.includes("red")
                      ? "text-red-600 dark:text-red-400"
                      : "text-gray-400"
                }`}
              >
                {config.icon} {config.label}
              </span>
            </motion.li>
          );
        })}
      </ul>
    </section>
  );
}
