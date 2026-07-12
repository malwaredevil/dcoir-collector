import fs from 'node:fs';
import path from 'node:path';
import { writeJson, nowIso, safeName } from '../../shared/dcoir_ui_common.mjs';

export const state = {
  args: null,
  outputDir: null,
  logPath: null
};

export function setRuntime(nextState) {
  state.args = nextState.args;
  state.outputDir = nextState.outputDir;
  state.logPath = nextState.logPath;
}

export function log(message, obj) {
  const line = `${nowIso()} ${message}${obj ? ' ' + JSON.stringify(obj) : ''}`;
  fs.appendFileSync(state.logPath, line + '\n', 'utf8');
  console.log(line);
}

export async function getVisibleDomSnapshot(page) {
  return await page.evaluate(() => {
    const elements = Array.from(document.querySelectorAll('button, [role="button"], input, textarea, [aria-label], [placeholder], div, span, a')).slice(0, 3000);
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    return elements.filter(visible).map((el) => {
      const box = el.getBoundingClientRect();
      return {
        tag: el.tagName,
        role: el.getAttribute('role'),
        aria: el.getAttribute('aria-label'),
        placeholder: el.getAttribute('placeholder'),
        type: el.getAttribute('type'),
        text: (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 400),
        x: Math.round(box.x),
        y: Math.round(box.y),
        w: Math.round(box.width),
        h: Math.round(box.height)
      };
    }).filter(x => x.text || x.aria || x.placeholder || x.role || x.type).slice(0, 900);
  });
}

export async function captureSnapshot(page, label) {
  const fullLabel = state.args?.activeSnapshotPrefix ? `${state.args?.activeSnapshotPrefix}_${label}` : label;
  const payload = { timestamp_utc: nowIso(), label: fullLabel, url: page.url(), title: await page.title(), elements: await getVisibleDomSnapshot(page) };
  const domPath = path.join(state.outputDir, `${safeName(fullLabel)}.dom.json`);
  writeJson(domPath, payload);
  const result = { label: fullLabel, dom_evidence: domPath };
  if (state.args?.enableScreenshots) {
    const screenshotPath = path.join(state.outputDir, `${safeName(fullLabel)}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true });
    result.screenshot = screenshotPath;
  }
  return result;
}
