import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("../../../../packages/design-system/tokens.css", import.meta.url), "utf8");
const [light, darkPart] = css.split('[data-theme="dark"]');
const dark = darkPart.split("*:focus-visible")[0];

function color(block: string, name: string): string {
  const match = block.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!match) throw new Error(`Missing ${name}`);
  return match[1];
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((start) => parseInt(hex.slice(start, start + 2), 16) / 255);
  const linear = channels.map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
}

function contrast(first: string, second: string): number {
  const [low, high] = [luminance(first), luminance(second)].sort((a, b) => a - b);
  return (high + 0.05) / (low + 0.05);
}

describe("design token contrast", () => {
  for (const [theme, block] of [["light", light], ["dark", dark]] as const) {
    it(`${theme} text and primary actions meet normal text contrast`, () => {
      const pairs = [
        ["--pm-text", "--pm-surface"],
        ["--pm-text-muted", "--pm-surface"],
        ["--pm-primary-strong", "--pm-surface"],
        ["--pm-on-primary", "--pm-primary-strong"],
      ];
      for (const [foreground, background] of pairs) {
        expect(contrast(color(block, foreground), color(block, background)), `${foreground} on ${background}`).toBeGreaterThanOrEqual(4.5);
      }
    });
    it(`${theme} control boundaries remain distinguishable`, () => {
      for (const background of ["--pm-surface", "--pm-bg", "--pm-surface-muted"]) {
        expect(contrast(color(block, "--pm-border-strong"), color(block, background)), `control border on ${background}`).toBeGreaterThanOrEqual(3);
      }
    });
  }
});
