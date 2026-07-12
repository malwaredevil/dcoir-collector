import path from 'node:path';
import { getRuntime, nowIso, safeName, writeJson } from './airtable_wbs09_ui_views_runtime.mjs';

export async function clickFirst(page, candidates, options = {}) {
  const timeout = options.timeout ?? 2000;
  for (const candidate of candidates) {
    try {
      const loc = typeof candidate === 'string' ? page.locator(candidate).first() : candidate.first();
      if (await loc.count()) {
        await loc.click({ timeout });
        return { ok: true, selector: String(candidate) };
      }
    } catch (_) {}
  }
  return { ok: false };
}

export async function getVisibleDomSnapshot(page) {
  return await page.evaluate(() => {
    const elements = Array.from(document.querySelectorAll('button, [role="button"], input, textarea, [aria-label], [placeholder], div, span, a')).slice(0, 2500);
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
        text: (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 300),
        x: Math.round(box.x),
        y: Math.round(box.y),
        w: Math.round(box.width),
        h: Math.round(box.height)
      };
    }).filter(x => x.text || x.aria || x.placeholder || x.role || x.type).slice(0, 700);
  });
}

export async function captureSnapshot(page, outputDir, label) {
  const payload = { timestamp_utc: nowIso(), label, url: page.url(), title: await page.title(), elements: await getVisibleDomSnapshot(page) };
  const domPath = path.join(outputDir, `${safeName(label)}.dom.json`);
  writeJson(domPath, payload);
  const result = { label, dom_evidence: domPath };
  if (getRuntime().args.enableScreenshots) {
    const screenshotPath = path.join(outputDir, `${safeName(label)}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true });
    result.screenshot = screenshotPath;
  }
  return result;
}

export async function captureDomEvidence(page, outputDir, index, view, reason, result) {
  const base = `failure_${String(index).padStart(3, '0')}_${safeName(view.table_name)}_${safeName(view.view_name)}_${safeName(reason)}`;
  if (getRuntime().args.enableScreenshots) {
    const screenshotPath = path.join(outputDir, `${base}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true });
    result.screenshot = screenshotPath;
  }
  const dom = await getVisibleDomSnapshot(page);
  const domPath = path.join(outputDir, `${base}.dom.json`);
  writeJson(domPath, { timestamp_utc: nowIso(), reason, url: page.url(), title: await page.title(), elements: dom });
  result.dom_evidence = domPath;
}

export async function clickVisibleTextFallback(page, pattern, label, options = {}) {
  const timeout = options.timeout ?? 3000;
  const handle = await page.evaluateHandle((source) => {
    const re = new RegExp(source, 'i');
    const elements = Array.from(document.querySelectorAll('button, [role="button"], div, span, a'));
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    for (const el of elements) {
      const text = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
      if (visible(el) && re.test(text)) return el;
    }
    return null;
  }, pattern.source);
  const el = handle.asElement();
  if (!el) return { ok: false };
  await el.click({ timeout });
  return { ok: true, selector: `visible-text-fallback:${label}` };
}
