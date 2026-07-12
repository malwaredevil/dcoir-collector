import { exactTextPattern } from './airtable_wbs09_apply_validation_due_view_contract.mjs';

export async function clickVisibleText(page, pattern, label, bounds = {}) {
  const source = pattern instanceof RegExp ? pattern.source : String(pattern);
  const flags = pattern instanceof RegExp ? pattern.flags : 'i';
  const picked = await page.evaluate(({ source, flags, label, bounds }) => {
    const re = new RegExp(source, flags.includes('i') ? 'i' : undefined);
    const normalize = (s) => String(s || '').replace(/[\u2192\u27f6\u2794]/g, ' -> ').replace(/\s+/g, ' ').trim();
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    function clickableAncestor(el) {
      let cur = el;
      for (let i = 0; cur && i < 8; i += 1) {
        const tag = cur.tagName;
        const role = cur.getAttribute('role');
        if (tag === 'BUTTON' || tag === 'A' || role === 'button' || role === 'option' || role === 'menuitem' || cur.onclick) return cur;
        cur = cur.parentElement;
      }
      return el;
    }
    const xMin = Number(bounds.xMin ?? 250);
    const xMax = Number(bounds.xMax ?? window.innerWidth);
    const yMin = Number(bounds.yMin ?? 90);
    const yMax = Number(bounds.yMax ?? window.innerHeight);
    const nodes = Array.from(document.querySelectorAll('[role="option"], [role="menuitem"], button, [role="button"], div, span, a, input'));
    const candidates = nodes.map((el) => {
      const box = el.getBoundingClientRect();
      const text = normalize(el.innerText || el.textContent || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.value || '');
      const role = el.getAttribute('role') || '';
      return { el, text, role, x: box.x, y: box.y, w: box.width, h: box.height, area: box.width * box.height };
    }).filter((c) => {
      if (!visible(c.el)) return false;
      if (!c.text || c.text.length > 160) return false;
      if (c.x < xMin || c.x > xMax || c.y < yMin || c.y > yMax) return false;
      if (c.w < 8 || c.h < 8 || c.w > 800 || c.h > 100) return false;
      return re.test(c.text);
    }).sort((a, b) => {
      const ar = /^(option|menuitem|button)$/i.test(a.role) ? 0 : 1;
      const br = /^(option|menuitem|button)$/i.test(b.role) ? 0 : 1;
      return ar - br || a.area - b.area || a.y - b.y || a.x - b.x;
    });
    const c = candidates[0];
    if (!c) return null;
    const target = clickableAncestor(c.el);
    const box = target.getBoundingClientRect();
    target.click();
    return { selector: `visible-text:${label}`, text: c.text, role: c.role, x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width), h: Math.round(box.height), cx: Math.round(box.x + box.width / 2), cy: Math.round(box.y + box.height / 2) };
  }, { source, flags, label, bounds });
  return picked ? { ok: true, ...picked } : { ok: false, selector: `visible-text:${label}` };
}

export async function clickAt(page, point, label) {
  await page.mouse.click(Math.round(point.x), Math.round(point.y));
  return { ok: true, selector: `coordinate:${label}`, x: Math.round(point.x), y: Math.round(point.y) };
}

export async function keyboardSelectAt(page, point, value, label) {
  const opened = await clickAt(page, point, `${label}-open`);
  await page.waitForTimeout(450);
  await page.keyboard.type(String(value), { delay: 15 });
  await page.waitForTimeout(550);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(900);
  return { ok: true, selector: `${opened.selector}+keyboard-select`, value };
}

export async function clickOpenOptionExact(page, value, label, bounds = {}) {
  const exact = exactTextPattern(value);
  let clicked = await clickVisibleText(page, exact, label, bounds);
  if (clicked.ok) return clicked;
  await page.keyboard.type(String(value), { delay: 15 });
  await page.waitForTimeout(500);
  clicked = await clickVisibleText(page, exact, `${label}-after-typeahead`, bounds);
  if (clicked.ok) return clicked;
  await page.keyboard.press('Enter').catch(() => {});
  await page.waitForTimeout(700);
  return { ok: true, selector: `keyboard-typeahead-enter:${label}`, value };
}

export function pointFromPanel(panel, relX, fallbackY) {
  if (!panel) return { x: relX, y: fallbackY };
  return { x: panel.x + relX, y: fallbackY ?? panel.y + 138 };
}

export function rowYFromExtraction(extracted, fallback) {
  const rows = Array.isArray(extracted?.rows) ? extracted.rows : [];
  const row = rows.find((candidate) => /where|review_after|is on or before|today/i.test(String(candidate.text || '')) && !/add condition/i.test(String(candidate.text || '')));
  return Number(row?.y || fallback || 268);
}
