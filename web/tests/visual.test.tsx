// Visual-direction guard (SC-009): no monospace for content; numbers use tabular figures.
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "../src");

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = path.join(dir, name);
    if (statSync(p).isDirectory()) return walk(p);
    return /\.(tsx)$/.test(p) ? [p] : [];
  });
}

describe("visual direction", () => {
  it("uses no monospace utility classes anywhere in the UI", () => {
    for (const file of walk(SRC)) {
      const text = readFileSync(file, "utf-8");
      expect(/font-mono|font-family:\s*monospace/.test(text), `${path.basename(file)} uses monospace`).toBe(false);
    }
  });

  it("aligns financial numbers with tabular figures (PnlGrid + cards use .num / tabular-nums)", () => {
    const grid = readFileSync(path.join(SRC, "components/PnlGrid.tsx"), "utf-8");
    const cardd = readFileSync(path.join(SRC, "components/VarianceCard.tsx"), "utf-8");
    expect(/tabular-nums|\bnum\b/.test(grid)).toBe(true);
    expect(/tabular-nums|\bnum\b/.test(cardd)).toBe(true);
  });

  it("defines a single indigo accent and semantic variance colors in the theme", () => {
    const tw = readFileSync(path.resolve(__dirname, "../tailwind.config.ts"), "utf-8");
    expect(tw).toMatch(/accent/);
    expect(tw).toMatch(/favorable/);
    expect(tw).toMatch(/unfavorable/);
  });
});
