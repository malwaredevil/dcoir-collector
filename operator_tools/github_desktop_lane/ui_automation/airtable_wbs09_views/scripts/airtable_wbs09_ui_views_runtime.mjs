import fs from 'node:fs';

export const VERSION = '2026-05-09.draft11-narrow-toolbar-buttons';

const runtime = {
  args: null,
  outputDir: null,
  logPath: null
};

export function setRuntime(nextRuntime) {
  Object.assign(runtime, nextRuntime);
}

export function getRuntime() {
  return runtime;
}

export function ensureDir(p) { fs.mkdirSync(p, { recursive: true }); }
export function writeJson(p, obj) { fs.writeFileSync(p, JSON.stringify(obj, null, 2), 'utf8'); }
export function nowIso() { return new Date().toISOString(); }
export function safeName(s) { return String(s).replace(/[^A-Za-z0-9_.-]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 120) || 'item'; }

export function log(message, obj) {
  const line = `${nowIso()} ${message}${obj ? ' ' + JSON.stringify(obj) : ''}`;
  fs.appendFileSync(runtime.logPath, line + '\n', 'utf8');
  console.log(line);
}
