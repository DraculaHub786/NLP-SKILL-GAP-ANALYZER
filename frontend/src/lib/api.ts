/**
 * Typed API client for the backend (Phase 5 integration).
 *
 * Every call throws ApiError with a user-presentable message so the UI can
 * render a designed error state (never a silent console error).
 */
import axios, { AxiosError } from "axios";
import type { ExtractedSkills, GapReport } from "../types/gapReport";
import type { ResumeIntelligenceReport } from "../types/resumeIntelligenceReport";

export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8080/api/v1";

export class ApiError extends Error {
  readonly status: number | null;

  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ detail?: string }>;
    const detail = axiosError.response?.data?.detail;
    if (typeof detail === "string" && detail) {
      return new ApiError(detail, axiosError.response?.status ?? null);
    }
    if (!axiosError.response) {
      return new ApiError(
        "Could not reach the analysis service. Check your connection and try again.",
        null
      );
    }
    return new ApiError(
      "Something went wrong while analyzing. Please try again.",
      axiosError.response.status
    );
  }
  return new ApiError("Something went wrong while analyzing. Please try again.", null);
}

export async function parseResume(file: File): Promise<ExtractedSkills> {
  const form = new FormData();
  form.append("file", file);
  try {
    const response = await axios.post<ExtractedSkills>(`${API_BASE}/parse/resume`, form);
    return response.data;
  } catch (error) {
    throw toApiError(error);
  }
}

export async function parseJd(text: string): Promise<ExtractedSkills> {
  const form = new FormData();
  form.append("text", text);
  try {
    const response = await axios.post<ExtractedSkills>(`${API_BASE}/parse/jd`, form);
    return response.data;
  } catch (error) {
    throw toApiError(error);
  }
}

export async function analyzeGap(
  resumeSkills: string[],
  jdSkills: string[]
): Promise<GapReport> {
  try {
    const response = await axios.post<GapReport>(`${API_BASE}/analyze`, {
      resume_skills: resumeSkills,
      jd_skills: jdSkills,
    });
    return response.data;
  } catch (error) {
    throw toApiError(error);
  }
}

/** Unified 3-engine analysis: ATS + Content + optional JD Match in one call. */
export async function analyzeResume(
  file: File,
  jdText?: string
): Promise<ResumeIntelligenceReport> {
  const form = new FormData();
  form.append("file", file);
  if (jdText && jdText.trim()) {
    form.append("jd_text", jdText);
  }
  try {
    const response = await axios.post<ResumeIntelligenceReport>(
      `${API_BASE}/analyze/resume`,
      form
    );
    return response.data;
  } catch (error) {
    throw toApiError(error);
  }
}
