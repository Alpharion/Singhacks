#!/usr/bin/env node
// Cursor `stop` hook.
//
// Fires when Cursor's agent loop finishes. It returns a followup_message,
// which Cursor auto-submits to its own model as the next user message. Cursor's
// built-in model then judges the turn and, if warranted, runs submit.mjs.
// No external LLM is called.
//
// loop_count guards against an endless loop: on the injected follow-up turn
// loop_count is greater than 0, so we return nothing and let it stop. Also set
// loop_limit in hooks.json as a hard cap (see hooks.snippet.json).

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildInstruction } from "../../reflection.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const submitPath = path.resolve(here, "../../submit.mjs");

function emit(obj) {
  process.stdout.write(JSON.stringify(obj));
  process.exit(0);
}

let input = {};
try {
  const stdin = fs.readFileSync(0, "utf8");
  if (stdin.trim()) input = JSON.parse(stdin);
} catch {
  emit({});
}

// Do not inject again on our own follow-up turn.
if (Number(input.loop_count || 0) > 0) emit({});

// Optional sampling (0 to 1). Default 1 = every turn.
let sample = process.env.XRPL_FEEDBACK_SAMPLE;
try {
  const cfgPath =
    process.env.XRPL_FEEDBACK_CONFIG ||
    path.join(os.homedir(), ".xrpl-feedback-hook.json");
  if (sample === undefined && fs.existsSync(cfgPath)) {
    sample = JSON.parse(fs.readFileSync(cfgPath, "utf8")).sample;
  }
} catch {
  // ignore
}
if (sample !== undefined && sample !== null && sample !== "") {
  const rate = Number(sample);
  if (!Number.isNaN(rate) && Math.random() > rate) emit({});
}

emit({ followup_message: buildInstruction(submitPath) });
