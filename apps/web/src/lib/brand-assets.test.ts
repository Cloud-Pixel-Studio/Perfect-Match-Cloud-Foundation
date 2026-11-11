import { existsSync, readFileSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const publicRoot = resolve(process.cwd(), "public");

const requiredAssets = [
  "brand/selected/pmqms-mark.svg",
  "brand/selected/pmqms-mark-dark.svg",
  "brand/selected/pmqms-mark-mono.svg",
  "brand/selected/pmqms-horizontal.svg",
  "brand/selected/pmqms-vertical.svg",
  "brand/selected/pm-monogram.svg",
  "brand/selected/favicon.svg",
  "brand/selected/app-icon.svg",
  "brand/raster/app-icon-192.png",
  "brand/raster/app-icon-512.png",
  "brand/raster/apple-touch-icon.png",
  "brand/raster/brand-board-1440.png",
  "brand/hero-quality-network.png",
  "brand/social/raster/og-perfect-match-qms-1200x630.png",
  "brand/social/raster/linkedin-company-1200.png",
] as const;

describe("brand asset contract", () => {
  it("ships every selected brand asset as a non-empty file", () => {
    for (const asset of requiredAssets) {
      const path = resolve(publicRoot, asset);
      expect(existsSync(path), asset).toBe(true);
      expect(statSync(path).size, asset).toBeGreaterThan(100);
    }
  });

  it("declares installable PWA icons and the official product name", () => {
    const manifest = JSON.parse(readFileSync(resolve(publicRoot, "manifest.webmanifest"), "utf8"));
    expect(manifest.name).toBe("Perfect Match QMS");
    expect(manifest.icons).toEqual(expect.arrayContaining([
      expect.objectContaining({ sizes: "192x192" }),
      expect.objectContaining({ sizes: "512x512" }),
    ]));
  });
});
