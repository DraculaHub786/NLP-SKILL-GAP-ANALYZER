import { useEffect, useReducer } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ThemeProvider } from "./context/ThemeContext";
import { UploadPage } from "./pages/UploadPage";
import { ResultsPage } from "./pages/ResultsPage";
import { PipelineStepper, type PipelineStage } from "./components/PipelineStepper";
import { sweepExpired, saveTemp } from "./lib/tempStore";
import { analyzeGap, parseJd, parseResume, ApiError } from "./lib/api";
import type { GapReport } from "./types/gapReport";

type Stage = "upload" | "analyzing" | "results";

interface AnalysisState {
  stage: Stage;
  report: GapReport | null;
  activePipelineStage: PipelineStage;
  errorStage: PipelineStage | null;
  errorMessage: string | null;
  lastResume: File | null;
  lastJdText: string;
}

const initialState: AnalysisState = {
  stage: "upload",
  report: null,
  activePipelineStage: "resume",
  errorStage: null,
  errorMessage: null,
  lastResume: null,
  lastJdText: "",
};

type AnalysisAction =
  | { type: "start"; resume: File; jdText: string }
  | { type: "stage"; pipelineStage: PipelineStage }
  | { type: "success"; report: GapReport }
  | { type: "error"; errorStage: PipelineStage; errorMessage: string }
  | { type: "retry" }
  | { type: "reset" };

function analysisReducer(state: AnalysisState, action: AnalysisAction): AnalysisState {
  switch (action.type) {
    case "start":
      return {
        ...state,
        stage: "analyzing",
        report: null,
        activePipelineStage: "resume",
        errorStage: null,
        errorMessage: null,
        lastResume: action.resume,
        lastJdText: action.jdText,
      };
    case "stage":
      return { ...state, activePipelineStage: action.pipelineStage, errorStage: null, errorMessage: null };
    case "success":
      return { ...state, stage: "results", report: action.report };
    case "error":
      return {
        ...state,
        stage: "analyzing",
        errorStage: action.errorStage,
        errorMessage: action.errorMessage,
      };
    case "retry":
      return {
        ...state,
        activePipelineStage: "resume",
        errorStage: null,
        errorMessage: null,
        stage: "analyzing",
      };
    case "reset":
      return initialState;
  }
}

export default function App() {
  const [state, dispatch] = useReducer(analysisReducer, initialState);

  useEffect(() => {
    sweepExpired(); // purge anything past its 48h TTL on load
  }, []);

  async function runAnalysis(resume: File, jdText: string) {
    try {
      dispatch({ type: "stage", pipelineStage: "resume" });
      const resumeResult = await parseResume(resume);

      dispatch({ type: "stage", pipelineStage: "jd" });
      const jdResult = await parseJd(jdText);

      dispatch({ type: "stage", pipelineStage: "gap" });
      const report = await analyzeGap(resumeResult.skills, jdResult.skills);

      await saveTemp("last-report", report);
      dispatch({ type: "success", report });
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "Something went wrong while analyzing. Please try again.";
      // The stage we were processing when the request failed.
      dispatch({ type: "error", errorStage: state.activePipelineStage, errorMessage: message });
    }
  }

  function handleAnalyze(resume: File | null, jdText: string) {
    if (!resume) return;
    dispatch({ type: "start", resume, jdText });
    void runAnalysis(resume, jdText);
  }

  function handleRetry() {
    if (!state.lastResume) return;
    dispatch({ type: "retry" });
    void runAnalysis(state.lastResume, state.lastJdText);
  }

  return (
    <ThemeProvider>
      <AnimatePresence mode="wait">
        {state.stage === "upload" && (
          <motion.div key="upload" exit={{ opacity: 0, y: -8 }}>
            <UploadPage onAnalyze={handleAnalyze} />
          </motion.div>
        )}
        {state.stage === "analyzing" && (
          <motion.div
            key="analyzing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="min-h-screen flex items-center justify-center bg-white dark:bg-[#121212] text-gray-800 dark:text-gray-100 px-6"
          >
            <PipelineStepper
              activeStage={state.activePipelineStage}
              errorStage={state.errorStage}
              errorMessage={state.errorMessage}
              onRetry={handleRetry}
            />
          </motion.div>
        )}
        {state.stage === "results" && state.report && (
          <motion.div key="results" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <ResultsPage report={state.report} onReset={() => dispatch({ type: "reset" })} />
          </motion.div>
        )}
      </AnimatePresence>
    </ThemeProvider>
  );
}
