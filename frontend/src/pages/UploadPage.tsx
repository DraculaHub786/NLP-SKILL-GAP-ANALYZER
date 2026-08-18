import { useState, useRef, useCallback } from "react";
import { motion } from "framer-motion";
import { useTheme } from "../context/ThemeContext";

interface UploadPageProps {
  onAnalyze: (resume: File | null, jdText: string) => void;
}

export function UploadPage({ onAnalyze }: UploadPageProps) {
  const { theme, toggle } = useTheme();
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jdText, setJdText] = useState("");
  const [isDragActive, setIsDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const canAnalyze = Boolean(resumeFile);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file && (file.name.endsWith(".pdf") || file.name.endsWith(".docx"))) {
      setResumeFile(file);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragActive(true);
  }, []);

  const handleDragLeave = useCallback(() => setIsDragActive(false), []);

  const fileSize = resumeFile
    ? resumeFile.size > 1024 * 1024
      ? `${(resumeFile.size / (1024 * 1024)).toFixed(1)} MB`
      : `${(resumeFile.size / 1024).toFixed(0)} KB`
    : "";

  return (
    <div className="min-h-screen bg-surface-canvas dark:bg-surface-dark text-ink-primary dark:text-ink-onDark px-6 py-10 transition-colors">
      <div className="max-w-3xl mx-auto">
        <div className="flex justify-between items-center mb-10">
          <h1 className="text-2xl font-semibold tracking-tight">SkillGap AI</h1>
          <button
            onClick={toggle}
            className="px-3 py-1.5 rounded-xl2 text-sm border border-surface-sunken dark:border-surface-darkCard hover:bg-surface-sunken dark:hover:bg-surface-darkCard transition active:scale-[0.98]"
          >
            {theme === "light" ? "🌙 Dark" : "☀️ Light"}
          </button>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="grid md:grid-cols-2 gap-6"
        >
          {/* Drop zone */}
          <div
            onClick={() => inputRef.current?.click()}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            className={`border-2 border-dashed rounded-xl2 p-8 text-center cursor-pointer transition-all ${
              isDragActive
                ? "border-accent bg-accent-subtle/30 dark:bg-accent/10"
                : resumeFile
                  ? "border-status-success/40 bg-status-success/5"
                  : "border-surface-sunken dark:border-surface-darkCard hover:border-accent/50 bg-surface-sunken/30 dark:bg-surface-darkCard/50"
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
            />
            {resumeFile ? (
              <div className="space-y-2">
                <p className="text-2xl">📄</p>
                <p className="font-medium text-ink-primary dark:text-ink-onDark">{resumeFile.name}</p>
                <p className="text-xs text-ink-muted">{fileSize}</p>
                <button
                  onClick={(e) => { e.stopPropagation(); setResumeFile(null); }}
                  className="text-xs text-status-critical hover:underline"
                >
                  Remove
                </button>
              </div>
            ) : (
              <>
                <p className="text-2xl mb-2">📎</p>
                <p className="font-medium text-ink-primary dark:text-ink-onDark">Drop your resume here</p>
                <p className="text-sm text-ink-muted mt-1">PDF or DOCX</p>
              </>
            )}
          </div>

          {/* JD textarea */}
          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="Paste the job description here..."
            className="border-2 border-surface-sunken dark:border-surface-darkCard rounded-xl2 p-4 h-40 md:h-full resize-none bg-surface-card dark:bg-surface-darkCard text-ink-primary dark:text-ink-onDark placeholder-ink-muted focus:outline-none focus:border-accent transition"
          />
        </motion.div>

        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={() => onAnalyze(resumeFile, jdText)}
          disabled={!canAnalyze}
          className="mt-8 w-full py-3 rounded-xl2 bg-accent text-white font-medium disabled:opacity-40 hover:bg-accent-hover hover:shadow-liftHover transition active:scale-[0.98]"
        >
          Analyze Gap
        </motion.button>

        <p className="text-xs text-ink-muted mt-4 text-center">
          Your data auto-deletes in 48h — nothing is stored on our servers.
        </p>
      </div>
    </div>
  );
}
