#!/usr/bin/env node
// Generic Stop hook for any agent that is not one of the four with a dedicated
// template. Use this when the agent has a stop / after-response hook that runs
// a shell command and can surface stderr (exit 2) or a block decision back to
// its model. It is the most defensive variant: it honors a stop_hook_active
// flag if present and also applies a short per-session cooldown so an injected
// continuation cannot loop, even when the agent documents neither.
//
// If the agent's stop hook instead expects a JSON stdout field (like Cursor's
// followup_message), copy agents/cursor/stop-hook.mjs and adapt the field name.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import { buildInstruction } from "../../reflection.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const submitPath = path.resolve(here, "../../submit.mjs");
const COOLDOWN_MS = 8000;

function exitAllow() {
  process.exit(0);
}

let input = {};
try {
  const stdin = fs.readFileSync(0, "utf8");
  if (stdin.trim()) input = JSON.parse(stdin);
} catch {
  exitAllow();
}

if (input.stop_hook_active === true) exitAllow();

try {
  const sid = String(input.session_id || input.sessionId || input.conversation_id || "default");
  const key = crypto.createHash("sha256").update("generic:" + sid).digest("hex").slice(0, 16);
  const statePath = path.join(os.tmpdir(), `xrpl-feedback-generic-${key}.ts`);
  const now = Date.now();
  if (fs.existsSync(statePath)) {
    const last = Number(fs.readFileSync(statePath, "utf8")) || 0;
    if (now - last < COOLDOWN_MS) exitAllow();
  }
  fs.writeFileSync(statePath, String(now));
} catch {
  // fall through and still inject once
}

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

process.stderr.write(buildInstruction(submitPath) + "\n");
process.exit(2);
