// Verify public evidence hashes. Optional raw verification requires the retained local artifacts.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { resolve, sep } from "node:path";

const root = process.cwd();
const manifest = JSON.parse(await readFile(resolve(root, "docs/audits/2026-11-14/FLOW_EVIDENCE_MANIFEST.json"), "utf8"));
assert.equal(manifest.schema_version, 2);
async function verify(entries, prefix) {
  assert(Array.isArray(entries));
  assert.equal(new Set(entries.map(entry => entry.path)).size, entries.length);
  for (const entry of entries) {
    assert(typeof entry.path === "string" && entry.path.startsWith(prefix) && !entry.path.split("/").includes(".."));
    assert(/^[0-9a-f]{64}$/.test(entry.sha256));
    const path = resolve(root, entry.path);
    assert(path.startsWith(root + sep));
    assert.equal(createHash("sha256").update(await readFile(path)).digest("hex"), entry.sha256, entry.path);
  }
  return entries.length;
}
const publicCount = await verify(manifest.files, "docs/audits/2026-11-14/");
const rawCount = process.env.FLOW_VERIFY_RAW === "1" ? await verify(manifest.raw_artifacts, "artifacts/complete-flow-audit-20261114/") : "not requested";
console.log(JSON.stringify({ result: "PASS", publicFiles: publicCount, rawFiles: rawCount, note: "Integrity only; no identity signature or QMS approval." }));
