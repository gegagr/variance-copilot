// CONSTITUTION guard: the UI computes no financial figure. It must never coerce a served figure
// string back into a number (parseFloat/Number) or reformat it (toLocaleString). Figures arrive
// pre-formatted from deterministic Python and are rendered verbatim.
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = path.resolve(__dirname, "../src");
const FORBIDDEN = [/\bparseFloat\s*\(/, /\bNumber\s*\(/, /\.toLocaleString\s*\(/, /\bparseInt\s*\(/];

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = path.join(dir, name);
    if (statSync(p).isDirectory()) return walk(p);
    return /\.(ts|tsx)$/.test(p) && !p.endsWith("types.ts") ? [p] : [];
  });
}

describe("no figure arithmetic in the UI", () => {
  const files = walk(path.join(ROOT, "components")).concat([
    path.join(ROOT, "lib", "format.ts"),
    path.join(ROOT, "lib", "anchor.ts"),
  ]);

  it.each(files)("%s contains no figure coercion/reformatting", (file) => {
    const text = readFileSync(file, "utf-8");
    for (const re of FORBIDDEN) {
      expect(re.test(text), `${path.basename(file)} matches ${re}`).toBe(false);
    }
  });
});
