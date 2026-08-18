/// <reference types="node" />

import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";
import os from "node:os";
import path from "node:path";
import { writeFileSync, mkdirSync } from "node:fs";

// The sample resume fixture ships with the backend tests.
const fixturePath = fileURLToPath(
  new URL("../../backend/tests/fixtures/sample_resume.pdf", import.meta.url)
);

const JD_TEXT = [
  "We are looking for a senior software engineer.",
  "Must have strong Python, SQL, and Docker skills.",
  "Experience with React, TypeScript, and REST APIs is a plus.",
  "Requirements: distributed systems, AWS, Kubernetes.",
].join("\n");

test("upload resume + JD → results screen with a match score", async ({ page }) => {
  await page.goto("/");

  // Attach the real sample PDF.
  await page.setInputFiles('input[type="file"]', fixturePath);

  // Paste the JD.
  await page.fill("textarea", JD_TEXT);

  // Kick off the analysis.
  await page.getByRole("button", { name: "Analyze Gap" }).click();

  // The staged pipeline stepper should appear and resolve to the results.
  await expect(page.getByRole("status")).toBeVisible();
  await page.waitForURL((url) => true, { timeout: 500 }).catch(() => {}); // no route change expected

  // Results screen renders with a score ring and section headings.
  await expect(page.getByText("%", { exact: false }).first()).toBeVisible({ timeout: 30000 });
  await expect(page.getByText("Matched skills")).toBeVisible();
  await expect(page.getByText("Overall match with this role")).toBeVisible();

  // The sample resume contains Python — it should appear somewhere on screen.
  await expect(page.getByText("Python").first()).toBeVisible();
});

test("unsupported .txt upload shows a designed error state", async ({ page }) => {
  await page.goto("/");

  const txtPath = path.join(os.tmpdir(), "skillgap-unsupported-resume.txt");
  writeFileSync(txtPath, "plain text resume, not supported", "utf-8");

  await page.setInputFiles('input[type="file"]', txtPath);
  await page.fill("textarea", JD_TEXT);
  await page.getByRole("button", { name: "Analyze Gap" }).click();

  // The stepper error state appears with a user-presentable message.
  await expect(page.getByRole("status")).toBeVisible();
  await expect(page.getByText("Unsupported file type", { exact: false })).toBeVisible({ timeout: 30000 });
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});
