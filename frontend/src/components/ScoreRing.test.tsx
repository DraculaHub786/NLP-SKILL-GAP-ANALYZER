import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { ScoreRing } from "./ScoreRing";

// The count-up animation uses requestAnimationFrame which doesn't run in jsdom.
// Mock it to immediately invoke the callback so the animation completes.
beforeEach(() => {
  let id = 0;
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb: FrameRequestCallback) => {
    // Simulate immediate frame with timestamp 800ms in the future so animation completes
    cb(performance.now() + 800);
    return ++id;
  });
});

describe("ScoreRing", () => {
  it("renders the percentage rounded", async () => {
    render(<ScoreRing score={87.4} />);
    await waitFor(() => {
      expect(screen.getByText("87%")).toBeInTheDocument();
    });
  });

  it("renders 100% at the max score", async () => {
    render(<ScoreRing score={100} />);
    await waitFor(() => {
      expect(screen.getByText("100%")).toBeInTheDocument();
    });
  });

  it("renders 0% at the min score", () => {
    render(<ScoreRing score={0} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("clamps scores above 100", async () => {
    render(<ScoreRing score={120} />);
    await waitFor(() => {
      expect(screen.getByText("100%")).toBeInTheDocument();
    });
  });
});
