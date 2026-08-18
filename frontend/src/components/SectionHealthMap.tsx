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
    return { dot: "bg-status-success", label: "Present", icon: "✓", text: "text-status-success" };
  }
  if (status === "missing") {
    return { dot: "bg-status-critical", label: "Missing", icon: "✗", text: "text-status-critical" };
  }
  return { dot: "bg-ink-muted", label: "Not detected", icon: "?", text: "text-ink-muted" };
}

export function SectionHealthMap({ sectionSummary }: SectionHealthMapProps) {
  const sections = Object.keys(SECTION_LABELS);
  const presentCount = sections.filter((s) => sectionSummary[s] === "present").length;

  return (
    <section className="mb-10" aria-label="Section health">
      <h2 className="text-lg font-semibold tracking-tight mb-2">📑 Required sections</h2>
      <p className="text-xs text-ink-muted mb-4">
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
              className="flex items-center gap-3 rounded-xl2 bg-surface-card dark:bg-surface-darkCard shadow-soft px-3 py-2.5"
            >
              <span className={`shrink-0 w-2 h-2 rounded-full ${config.dot}`} />
              <span className="text-sm flex-1 text-ink-primary dark:text-ink-onDark">{SECTION_LABELS[key]}</span>
              <span className={`text-xs font-medium ${config.text}`}>
                {config.icon} {config.label}
              </span>
            </motion.li>
          );
        })}
      </ul>
    </section>
  );
}
