import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

type ManifestItem = { path: string; sha256: string; width?: number; height?: number };
type Manifest = { approvalState: string; sources: ManifestItem[]; assets: ManifestItem[] };

const root = path.resolve(process.cwd(), "public/brand/design-studio");
const manifest = JSON.parse(
  readFileSync(path.join(root, "asset-manifest.json"), "utf8"),
) as Manifest;

function sha256(file: Buffer): string {
  return createHash("sha256").update(file).digest("hex");
}

describe("design studio asset manifest", () => {
  it("keeps every source and output bound to its recorded SHA-256", () => {
    for (const item of [...manifest.sources, ...manifest.assets]) {
      const file = readFileSync(path.join(root, item.path));
      expect(sha256(file), item.path).toBe(item.sha256);
    }
  });

  it("records exact PNG dimensions and keeps the set in human review", () => {
    expect(manifest.approvalState).toBe("draft_requires_human_review");
    expect(manifest.assets).toHaveLength(6);
    for (const item of manifest.assets) {
      const file = readFileSync(path.join(root, item.path));
      expect(file.subarray(1, 4).toString(), item.path).toBe("PNG");
      expect(file.readUInt32BE(16), `${item.path} width`).toBe(item.width);
      expect(file.readUInt32BE(20), `${item.path} height`).toBe(item.height);
    }
  });
});

