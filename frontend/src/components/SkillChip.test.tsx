import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SkillChip } from "./SkillChip";

describe("SkillChip", () => {
  it("renders the label", () => {
    render(<SkillChip label="Python" variant="matched" />);
    expect(screen.getByText("Python")).toBeInTheDocument();
  });

  it.each([
    ["matched", "bg-green-100"],
    ["missing", "bg-amber-100"],
    ["bonus", "bg-indigo-100"],
  ] as const)("renders the correct variant class for %s", (variant, expectedClass) => {
    render(<SkillChip label="Skill" variant={variant} />);
    expect(screen.getByText("Skill")).toHaveClass(expectedClass);
  });
});
