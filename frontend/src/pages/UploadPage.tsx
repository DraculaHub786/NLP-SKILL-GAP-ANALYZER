import { useState } from "react";
import { motion } from "framer-motion";
import { useTheme } from "../context/ThemeContext";

interface UploadPageProps {
  onAnalyze: (resume: File | null, jdText: string) => void;
}

export function UploadPage({ onAnalyze }: UploadPageProps) {
  const { theme, toggle } = useTheme();
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jdText, setJdText] = useState("");

  // A resume alone is enough — JD is optional (ATS + Content only mode).
  const canAnalyze = Boolean(resumeFile);

  return (
    <div className="min-h-screen bg-white dark:bg-[#121212] text-gray-800 dark:text-gray-100 px-6 py-10 transition-colors">
      <div className="max-w-3xl mx-auto">
        <div className="flex justify-between items-center mb-10">
          <h1 className="text-2xl font-semibold">SkillGap AI</h1>
          <button
            onClick={toggle}
            className="px-3 py-1.5 rounded-full text-sm border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
          >
            {theme === "light" ? "🌙 Dark" : "☀️ Light"}
          </button>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="grid md:grid-cols-2 gap-6"
        >
          <label className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-2xl p-8 text-center cursor-pointer hover:border-accent transition">
            <input
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
            />
            <p className="font-medium">Drop your resume here</p>
            <p className="text-sm text-gray-500 mt-1">
              {resumeFile ? resumeFile.name : "PDF or DOCX"}
            </p>
          </label>

          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="Paste the job description here..."
            className="border-2 border-gray-300 dark:border-gray-600 rounded-2xl p-4 h-40 md:h-full resize-none bg-transparent focus:outline-none focus:border-accent transition"
          />
        </motion.div>

        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={() => onAnalyze(resumeFile, jdText)}
          disabled={!canAnalyze}
          className="mt-8 w-full py-3 rounded-full bg-accent text-white font-medium disabled:opacity-40 hover:shadow-lg transition"
        >
          Analyze Gap
        </motion.button>

        <p className="text-xs text-gray-500 mt-4 text-center">
          Your data auto-deletes in 48h — nothing is stored on our servers.
        </p>
      </div>
    </div>
  );
}
