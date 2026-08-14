import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ThemeProvider } from "./context/ThemeContext";
import { UploadPage } from "./pages/UploadPage";
import { ResultsPage } from "./pages/ResultsPage";
import { sweepExpired, saveTemp, getTemp } from "./lib/tempStore";
import axios from "axios";

type Stage = "upload" | "analyzing" | "results";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8080/api/v1";

export default function App() {
  const [stage, setStage] = useState<Stage>("upload");
  const [report, setReport] = useState<any>(null);

  useEffect(() => {
    sweepExpired(); // purge anything past its 48h TTL on load
  }, []);

  async function handleAnalyze(resume: File | null, jdText: string) {
    if (!resume) return;
    setStage("analyzing");

    const form = new FormData();
    form.append("file", resume);
    const resumeRes = await axios.post(`${API_BASE}/parse/resume`, form);

    const jdForm = new FormData();
    jdForm.append("text", jdText);
    const jdRes = await axios.post(`${API_BASE}/parse/jd`, jdForm);

    const analysisRes = await axios.post(`${API_BASE}/analyze`, {
      resume_skills: resumeRes.data.skills,
      jd_skills: jdRes.data.skills,
    });

    await saveTemp("last-report", analysisRes.data);
    setReport(analysisRes.data);
    setStage("results");
  }

  return (
    <ThemeProvider>
      <AnimatePresence mode="wait">
        {stage === "upload" && (
          <motion.div key="upload" exit={{ opacity: 0, y: -8 }}>
            <UploadPage onAnalyze={handleAnalyze} />
          </motion.div>
        )}
        {stage === "analyzing" && (
          <motion.div
            key="analyzing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="min-h-screen flex items-center justify-center bg-white dark:bg-[#121212] text-gray-800 dark:text-gray-100"
          >
            <p className="text-lg animate-pulse">Analyzing skills…</p>
          </motion.div>
        )}
        {stage === "results" && report && (
          <motion.div key="results" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <ResultsPage report={report} />
          </motion.div>
        )}
      </AnimatePresence>
    </ThemeProvider>
  );
}
