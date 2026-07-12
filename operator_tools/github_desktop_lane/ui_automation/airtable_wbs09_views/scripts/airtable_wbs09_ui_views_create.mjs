import path from 'node:path';
import { getRuntime, nowIso, safeName } from './airtable_wbs09_ui_views_runtime.mjs';
import { captureDomEvidence, clickFirst, clickVisibleTextFallback } from './airtable_wbs09_ui_views_dom.mjs';

export async function clickSidebarCreateNew(page) {
  const picked = await page.evaluate(() => {
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    const candidates = Array.from(document.querySelectorAll('button, [role="button"]')).map((el) => {
      const box = el.getBoundingClientRect();
      const text = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
      return { el, text, x: box.x, y: box.y, w: box.width, h: box.height };
    }).filter((c) => visible(c.el) && /^\+?\s*Create new\.{0,3}\s*$/i.test(c.text) && c.x >= 40 && c.x < 360 && c.y >= 120 && c.w >= 80).sort((a, b) => a.y - b.y || a.x - b.x);
    const c = candidates[0];
    if (!c) return null;
    c.el.scrollIntoView({ block: 'center', inline: 'center' });
    c.el.click();
    return { selector: 'geometry:sidebar-create-new-button', text: c.text, x: Math.round(c.x), y: Math.round(c.y), w: Math.round(c.w), h: Math.round(c.h) };
  });
  return picked ? { ok: true, ...picked } : { ok: false };
}

export async function clickGridOptionFromCreateMenu(page) {
  const picked = await page.evaluate(() => {
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    function clickableAncestor(el) {
      let cur = el;
      for (let i = 0; cur && i < 5; i += 1) {
        const tag = cur.tagName;
        const role = cur.getAttribute('role');
        if (tag === 'BUTTON' || tag === 'A' || role === 'button' || cur.onclick) return cur;
        cur = cur.parentElement;
      }
      return el;
    }
    const nodes = Array.from(document.querySelectorAll('button, [role="button"], div, span, a'));
    const candidates = nodes.map((el) => {
      const box = el.getBoundingClientRect();
      const text = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
      return { el, text, x: box.x, y: box.y, w: box.width, h: box.height };
    }).filter((c) => visible(c.el) && /^Grid$/i.test(c.text) && c.x >= 40 && c.x < 520 && c.y >= 160 && c.w > 8 && c.h > 8).sort((a, b) => a.y - b.y || a.x - b.x);
    const c = candidates[0];
    if (!c) return null;
    const target = clickableAncestor(c.el);
    const targetBox = target.getBoundingClientRect();
    target.click();
    return { selector: 'geometry:create-menu-grid-option', text: c.text, x: Math.round(c.x), y: Math.round(c.y), w: Math.round(c.w), h: Math.round(c.h), target_x: Math.round(targetBox.x), target_y: Math.round(targetBox.y), target_w: Math.round(targetBox.width), target_h: Math.round(targetBox.height) };
  });
  return picked ? { ok: true, ...picked } : { ok: false };
}

export async function fillNewViewNameInput(page, viewName) {
  const handle = await page.evaluateHandle(() => {
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    const inputs = Array.from(document.querySelectorAll('input, textarea')).map((el) => {
      const box = el.getBoundingClientRect();
      const aria = el.getAttribute('aria-label') || '';
      const placeholder = el.getAttribute('placeholder') || '';
      const type = el.getAttribute('type') || '';
      return { el, aria, placeholder, type, x: box.x, y: box.y, w: box.width, h: box.height };
    }).filter((c) => {
      const label = `${c.aria} ${c.placeholder}`;
      if (!visible(c.el)) return false;
      if (/find a view/i.test(label)) return false;
      if (c.type && !/^(text|search)$/i.test(c.type)) return false;
      return c.w >= 40 && c.h >= 16;
    }).sort((a, b) => {
      const scoreA = (/view name|name/i.test(`${a.aria} ${a.placeholder}`) ? 0 : 1);
      const scoreB = (/view name|name/i.test(`${b.aria} ${b.placeholder}`) ? 0 : 1);
      return scoreA - scoreB || a.y - b.y || a.x - b.x;
    });
    const c = inputs[0];
    return c ? c.el : null;
  });
  const el = handle.asElement();
  if (!el) return { ok: false };
  const box = await el.boundingBox();
  await el.click({ timeout: 3000 });
  const modifier = process.platform === 'darwin' ? 'Meta' : 'Control';
  await page.keyboard.press(`${modifier}+A`);
  await page.keyboard.type(viewName, { delay: 10 });
  return { ok: true, selector: 'geometry:new-view-name-input-excluding-find-view', x: box ? Math.round(box.x) : null, y: box ? Math.round(box.y) : null, w: box ? Math.round(box.width) : null, h: box ? Math.round(box.height) : null };
}

export async function clickFinalCreateButton(page) {
  const picked = await page.evaluate(() => {
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    const buttons = Array.from(document.querySelectorAll('button, [role="button"]')).map((el) => {
      const box = el.getBoundingClientRect();
      const text = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
      const aria = el.getAttribute('aria-label') || '';
      const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true';
      return { el, text, aria, disabled, x: box.x, y: box.y, w: box.width, h: box.height };
    }).filter((c) => {
      const label = `${c.text} ${c.aria}`.trim();
      if (!visible(c.el) || c.disabled) return false;
      if (/^\+?\s*Create new\.{0,3}$/i.test(label)) return false;
      if (/Create new\.{0,3}\s+No matching views/i.test(label)) return false;
      return /^(Create|Create view|Create new view|Create grid view)$/i.test(c.text) || /Create view|Create new view|Create grid view/i.test(c.aria);
    }).sort((a, b) => b.y - a.y || b.x - a.x);
    const c = buttons[0];
    if (!c) return null;
    c.el.click();
    return { selector: 'geometry:final-create-button', text: c.text, aria: c.aria, x: Math.round(c.x), y: Math.round(c.y), w: Math.round(c.w), h: Math.round(c.h) };
  });
  if (picked) return { ok: true, ...picked };
  return await clickVisibleTextFallback(page, /\bCreate (new |grid )?view\b|^Create$/i, 'final create visible text', { timeout: 3000 });
}

export async function createGridViewAttempt(page, view, outputDir, index) {
  const result = { index, table_name: view.table_name, table_id: view.table_id, view_name: view.view_name, status: 'started', attempted_at_utc: nowIso(), notes: [] };
  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(250);
  await page.mouse.move(520, 90).catch(() => {});
  const tableClick = await clickFirst(page, [page.getByText(view.table_name, { exact: true }), `[title="${view.table_name.replace(/"/g, '\\"')}"]`, `text="${view.table_name.replace(/"/g, '\\"')}"`], { timeout: 3000 });
  if (!tableClick.ok) { result.status = 'needs_manual_table_selection'; result.notes.push(`Could not safely click table tab/name: ${view.table_name}.`); await captureDomEvidence(page, outputDir, index, view, 'table_selection_not_found', result); return result; }
  result.notes.push(`Selected table using ${tableClick.selector}`);
  await page.waitForTimeout(800);
  await page.keyboard.press('Escape').catch(() => {});
  await page.mouse.move(520, 90).catch(() => {});
  const createNew = await clickSidebarCreateNew(page);
  if (!createNew.ok) { result.status = 'selector_create_new_not_found'; result.notes.push('Could not find the left-sidebar Create new... button.'); await captureDomEvidence(page, outputDir, index, view, 'create_new_not_found', result); return result; }
  result.notes.push(`Clicked create-new control using ${createNew.selector} at x=${createNew.x}, y=${createNew.y}.`);
  await page.waitForTimeout(900);
  await page.mouse.move(520, 90).catch(() => {});
  const gridChoice = await clickGridOptionFromCreateMenu(page);
  if (!gridChoice.ok) { result.status = 'selector_grid_choice_not_found'; result.notes.push('Could not choose Grid from the create-new popup without touching the current Grid view control.'); await captureDomEvidence(page, outputDir, index, view, 'grid_choice_not_found', result); return result; }
  result.notes.push(`Selected create-menu Grid option using ${gridChoice.selector} at x=${gridChoice.x}, y=${gridChoice.y}.`);
  await page.waitForTimeout(1000);
  await page.mouse.move(520, 90).catch(() => {});
  const nameFill = await fillNewViewNameInput(page, view.view_name);
  if (!nameFill.ok) { result.status = 'selector_view_name_input_not_found'; result.notes.push('Could not find a new-view name input. The Find a view search box is intentionally excluded.'); await captureDomEvidence(page, outputDir, index, view, 'view_name_input_not_found', result); return result; }
  result.notes.push(`Filled view name using ${nameFill.selector} at x=${nameFill.x}, y=${nameFill.y}.`);
  await page.waitForTimeout(800);
  const finalCreate = await clickFinalCreateButton(page);
  if (!finalCreate.ok) { result.status = 'selector_final_create_not_found'; result.notes.push('Could not find final Create/Create view button safely. View name may be staged in UI but create was not clicked.'); await captureDomEvidence(page, outputDir, index, view, 'final_create_not_found', result); return result; }
  result.status = 'create_clicked_unverified';
  result.notes.push(`Clicked final create using ${finalCreate.selector}. Verify in Airtable before continuing.`);
  await page.waitForTimeout(1500);
  if (getRuntime().args.enableScreenshots) { const screenshotPath = path.join(outputDir, `after_${String(index).padStart(3, '0')}_${safeName(view.table_name)}_${safeName(view.view_name)}.png`); await page.screenshot({ path: screenshotPath, fullPage: true }); result.screenshot = screenshotPath; }
  return result;
}
