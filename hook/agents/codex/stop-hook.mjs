#!/usr/bin/env node
// Codex Stop hook.
//
// Codex fires a Stop hook when a turn completes, sends the event as JSON on
// stdin (with stop_hook_active and last_assistant_message), and lets the hook
// inject an instruction back into its own model via exit 2 + stderr (or a
// {"decision":"block","reason":...} stdout payload). We use exit 2 + stderr.
// Codex's built-in model then judges the turn and, if warranted, runs
// submit.mjs. No external LLM is called.
//
// Register in ~/.codex/hooks.json (see hooks.snippet.json).

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildInstruction } from "../../reflection.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const submitPath = path.resolve(here, "../../submit.mjs");

function exitAllow() {
  process.exit(0); // let the turn stop normally
}

let input = {};
try {
  const stdin = fs.readFileSync(0, "utf8");
  if (stdin.trim()) input = JSON.parse(stdin);
} catch {
  exitAllow();
}

// Already inside a hook-triggered continuation: allow the stop, never loop.
if (input.stop_hook_active === true) exitAllow();

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
  if (!Number.isNaN(rate) && Math.random() > rate) exitAllow();
}

// Inject the instruction and ask Codex to continue.
process.stderr.write(buildInstruction(submitPath) + "\n");
process.exit(2);
