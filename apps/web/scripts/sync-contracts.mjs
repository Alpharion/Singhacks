#!/usr/bin/env node
// Sync the frozen contract into apps/web.
//
// packages/contracts is owned by Person 4 and must never be edited from here.
// This script only READS it and writes inside apps/web:
//
//   packages/contracts/openapi.yaml   -> src/lib/contracts/generated.ts
//   packages/contracts/fixtures/*.json -> src/lib/demo/fixtures/
//
// Re-run it whenever Person 4 releases a new contract version:
//   pnpm sync:contracts
//
// TypeScript will then immediately flag anything in the UI that drifted.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, "..");
const contractsRoot = path.resolve(webRoot, "../../packages/contracts");

const openapiPath = path.join(contractsRoot, "openapi.yaml");
const fixturesSrc = path.join(contractsRoot, "fixtures");
const generatedOut = path.join(webRoot, "src/lib/contracts/generated.ts");
const fixturesOut = path.join(webRoot, "src/lib/demo/fixtures");

function fail(message) {
  console.error(`sync-contracts: ${message}`);
  process.exit(1);
}

if (!fs.existsSync(openapiPath)) {
  fail(`cannot find ${openapiPath}. Run this from apps/web in the SurplusFlow repo.`);
}
if (!fs.existsSync(fixturesSrc)) {
  fail(`cannot find ${fixturesSrc}.`);
}

// 1. Types from the OpenAPI document. Uses the Node API rather than the CLI so
// this works identically in git bash, PowerShell, and CI.
fs.mkdirSync(path.dirname(generatedOut), { recursive: true });
const ast = await openapiTS(pathToFileURL(openapiPath));

const banner = [
  "/**",
  " * GENERATED FILE - DO NOT EDIT.",
  " *",
  " * Source: packages/contracts/openapi.yaml (Contract Freeze v1.0.0, owned by Person 4).",
  " * Regenerate with: pnpm sync:contracts",
  " *",
  " * Friendly aliases live in ./types.ts - import from there, not from this file.",
  " */",
  "",
].join("\n");
fs.writeFileSync(generatedOut, banner + astToString(ast));

// 2. Fixtures, copied verbatim so the demo data stays byte-identical to the contract.
fs.rmSync(fixturesOut, { recursive: true, force: true });
fs.mkdirSync(fixturesOut, { recursive: true });

const copied = fs
  .readdirSync(fixturesSrc)
  .filter((name) => name.endsWith(".json"))
  .sort();

if (copied.length === 0) fail("no fixtures found to copy.");

for (const name of copied) {
  const raw = fs.readFileSync(path.join(fixturesSrc, name), "utf8");
  JSON.parse(raw); // fail loudly rather than shipping a broken fixture
  fs.writeFileSync(path.join(fixturesOut, name), raw);
}

fs.writeFileSync(
  path.join(fixturesOut, "README.md"),
  [
    "# Copied fixtures - do not edit",
    "",
    "Verbatim copies of `packages/contracts/fixtures/` (Person 4 owns the originals).",
    "Regenerate with `pnpm sync:contracts`. Edits here are overwritten.",
    "",
    "The XRPL addresses and transaction hashes in these files are synthetic,",
    "shape-valid placeholders. They are not funded accounts and are not evidence",
    "of settlement - which is why the UI shows a demo-data badge in fixture mode.",
    "",
  ].join("\n"),
);

console.log(`sync-contracts: types -> ${path.relative(webRoot, generatedOut)}`);
console.log(
  `sync-contracts: ${copied.length} fixtures -> ${path.relative(webRoot, fixturesOut)}`,
);
