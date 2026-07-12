import { norm } from '../../shared/dcoir_ui_common.mjs';

export async function clickFirst(page, candidates, options = {}) {
  const timeout = options.timeout ?? 2500;
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

export async function clickExistingView(page, viewName) {
  const picked = await page.evaluate((name) => {
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim();
    const nodes = Array.from(document.querySelectorAll('button, [role="button"], div, span, a'));
    const candidates = nodes.map((el) => {
      const box = el.getBoundingClientRect();
      return { el, text: norm(el.innerText || el.textContent), x: box.x, y: box.y, w: box.width, h: box.height };
    }).filter(c => visible(c.el) && c.text === name && c.x >= 40 && c.x < 420 && c.y >= 100 && c.w > 20 && c.h > 8).sort((a, b) => a.y - b.y || a.x - b.x);
    const c = candidates[0];
    if (!c) return null;
    c.el.scrollIntoView({ block: 'center', inline: 'center' });
    c.el.click();
    return { selector: 'geometry:existing-view-sidebar-row', text: c.text, x: Math.round(c.x), y: Math.round(c.y), w: Math.round(c.w), h: Math.round(c.h) };
  }, viewName);
  return picked ? { ok: true, ...picked } : { ok: false };
}

export async function clickToolbarButton(page, labelRegex, label) {
  const roleCandidatesByLabel = {
    filter: [/^Filter rows$/i, /^Filter$/i],
    sort: [/^Sort rows$/i, /^Sort$/i]
  };
  const candidates = roleCandidatesByLabel[label] || [labelRegex];
  for (const name of candidates) {
    const loc = page.getByRole('button', { name });
    const count = await loc.count().catch(() => 0);
    for (let i = 0; i < count; i += 1) {
      const item = loc.nth(i);
      const box = await item.boundingBox().catch(() => null);
      const visible = await item.isVisible().catch(() => false);
      if (!visible || !box) continue;
      if (box.y < 80 || box.y > 145 || box.x < 760 || box.x > 1320 || box.width < 10 || box.width > 180 || box.height < 10 || box.height > 40) continue;
      const text = norm(await item.innerText().catch(() => ''));
      const aria = await item.getAttribute('aria-label').catch(() => '');
      await item.click({ timeout: 3000 });
      return { ok: true, selector: `role-toolbar-button:${label}`, text, aria: aria || '', x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width), h: Math.round(box.height) };
    }
  }
  return { ok: false };
}

export async function clearExistingFilterConditions(page, result) {
  const removed = [];
  for (let attempt = 0; attempt < 8; attempt += 1) {
    const target = await page.evaluate(() => {
      function visible(el) {
        const style = window.getComputedStyle(el);
        const box = el.getBoundingClientRect();
        return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
      }
      const nodes = Array.from(document.querySelectorAll('button, [role="button"]'));
      const candidates = nodes.map((el) => {
        const box = el.getBoundingClientRect();
        const text = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
        const aria = el.getAttribute('aria-label') || '';
        return { el, text, aria, x: box.x, y: box.y, w: box.width, h: box.height };
      }).filter((c) => {
        if (!visible(c.el)) return false;
        const removeByAria = /^Remove item \d+$/i.test(c.aria) || /remove.*condition|delete.*condition/i.test(c.aria);
        const removeByGeometry = c.x >= 830 && c.x <= 940 && c.y >= 200 && c.y <= 380 && c.w >= 18 && c.w <= 40 && c.h >= 18 && c.h <= 40;
        return removeByAria || removeByGeometry;
      }).sort((a, b) => a.y - b.y || a.x - b.x);
      const c = candidates[0];
      if (!c) return null;
      c.el.click();
      return { aria: c.aria, text: c.text, x: Math.round(c.x), y: Math.round(c.y), w: Math.round(c.w), h: Math.round(c.h) };
    });
    if (!target) break;
    removed.push(target);
    await page.waitForTimeout(600);
  }
  result.steps.push({ action: 'clear_existing_filter_conditions', ok: true, removed_count: removed.length, removed });
  return removed;
}

export async function clickPanelText(page, pattern, label) {
  const picked = await page.evaluate(({ source, label }) => {
    const re = new RegExp(source, 'i');
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    function clickableAncestor(el) {
      let cur = el;
      for (let i = 0; cur && i < 7; i += 1) {
        const tag = cur.tagName;
        const role = cur.getAttribute('role');
        if (tag === 'BUTTON' || tag === 'A' || role === 'button' || cur.onclick) return cur;
        cur = cur.parentElement;
      }
      return el;
    }
    const nodes = Array.from(document.querySelectorAll('button, [role="button"], div, span, a, input'));
    const candidates = nodes.map((el) => {
      const box = el.getBoundingClientRect();
      const text = (el.innerText || el.textContent || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').replace(/\s+/g, ' ').trim();
      return { el, text, x: box.x, y: box.y, w: box.width, h: box.height };
    }).filter(c => visible(c.el) && c.x >= 400 && c.x <= 1100 && c.y >= 110 && c.y <= 900 && re.test(c.text)).sort((a, b) => (a.w * a.h) - (b.w * b.h) || a.y - b.y || a.x - b.x);
    const c = candidates[0];
    if (!c) return null;
    const target = clickableAncestor(c.el);
    const box = target.getBoundingClientRect();
    target.click();
    return { selector: `panel-text:${label}`, text: c.text, x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width), h: Math.round(box.height) };
  }, { source: pattern.source, label });
  return picked ? { ok: true, ...picked } : { ok: false };
}

export async function clickPanelCoordinate(page, x, y, label) {
  await page.mouse.click(x, y);
  return { ok: true, selector: `coordinate:${label}`, x, y };
}

export async function selectDropdownValue(page, candidateText, fallbackPoint, value, label) {
  let step = await clickPanelText(page, candidateText, `${label}-open-by-text`);
  if (!step.ok && fallbackPoint) step = await clickPanelCoordinate(page, fallbackPoint.x, fallbackPoint.y, `${label}-open-by-coordinate`);
  if (!step.ok) return { ok: false, selector: `unable:${label}-open` };
  await page.waitForTimeout(450);
  await page.keyboard.type(String(value), { delay: 15 });
  await page.waitForTimeout(550);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(700);
  return { ok: true, selector: `${step.selector}+keyboard-select`, value };
}
