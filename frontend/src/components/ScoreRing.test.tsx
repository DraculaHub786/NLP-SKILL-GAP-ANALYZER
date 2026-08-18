import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ScoreRing } from "./ScoreRing";

describe("ScoreRing", () => {
  it("renders the percentage rounded", () => {
    render(<ScoreRing score={87.4} />);
    expect(screen.getByText("87%")).toBeInTheDocument();
  });

  it("renders 100% at the max score", () => {
    render(<ScoreRing score={100} />);
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("renders 0% at the min score", () => {
    render(<ScoreRing score={0} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("clamps scores above 100", () => {
    render(<ScoreRing score={120} />);
    expect(screen.getByText("100%")).toBeInTheDocument();
  });
});
