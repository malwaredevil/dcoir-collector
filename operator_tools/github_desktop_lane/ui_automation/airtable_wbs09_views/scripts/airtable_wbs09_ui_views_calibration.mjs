import path from 'node:path';
import { nowIso, VERSION, writeJson } from './airtable_wbs09_ui_views_runtime.mjs';
import { captureSnapshot, clickFirst } from './airtable_wbs09_ui_views_dom.mjs';

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
    }).filter(c => visible(c.el) && c.text === name && c.x >= 40 && c.x < 360 && c.y >= 120 && c.w > 20 && c.h > 8).sort((a, b) => a.y - b.y || a.x - b.x);
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
    sort: [/^Sort rows$/i, /^Sort$/i],
    'hide-fields': [/^Hide fields$/i]
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
      const text = (await item.innerText().catch(() => '')).replace(/\s+/g, ' ').trim();
      const aria = await item.getAttribute('aria-label').catch(() => '');
      await item.click({ timeout: 3000 });
      return { ok: true, selector: `role-toolbar-button:${label}`, text, aria: aria || '', x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width), h: Math.round(box.height) };
    }
  }

  const payload = { source: labelRegex.source, label };
  const picked = await page.evaluate(({ source, label }) => {
    const re = new RegExp(source, 'i');
    const wanted = {
      filter: [{ aria: 'Filter rows', text: 'Filter' }],
      sort: [{ aria: 'Sort rows', text: 'Sort' }],
      'hide-fields': [{ aria: 'Hide fields', text: 'Hide fields' }]
    }[label] || [];

    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }

    const candidates = Array.from(document.querySelectorAll('button, [role="button"]')).map((el) => {
      const box = el.getBoundingClientRect();
      const text = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
      const aria = el.getAttribute('aria-label') || '';
      const role = el.getAttribute('role') || '';
      return { el, text, aria, role, x: box.x, y: box.y, w: box.width, h: box.height };
    }).filter((c) => {
      if (!visible(c.el)) return false;
      if (c.y < 80 || c.y > 145 || c.x < 760 || c.x > 1320 || c.w < 10 || c.w > 180 || c.h < 10 || c.h > 40) return false;
      const exact = wanted.some(w => c.aria === w.aria || c.text === w.text);
      return exact || re.test(`${c.text} ${c.aria}`);
    }).sort((a, b) => (a.w * a.h) - (b.w * b.h) || a.x - b.x);

    const c = candidates[0];
    if (!c) return null;
    c.el.click();
    return { selector: `geometry:narrow-toolbar-${label}`, text: c.text, aria: c.aria, x: Math.round(c.x), y: Math.round(c.y), w: Math.round(c.w), h: Math.round(c.h) };
  }, payload);

  return picked ? { ok: true, ...picked } : { ok: false };
}

export async function calibrateViewConfiguration(page, outputDir, view) {
  const result = { timestamp_utc: nowIso(), mode: 'calibrate_view_config_selectors', tool_version: VERSION, target: { table_name: view.table_name, table_id: view.table_id, view_name: view.view_name }, steps: [], snapshots: [] };
  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(300);
  const tableClick = await clickFirst(page, [page.getByText(view.table_name, { exact: true }), `[title="${view.table_name.replace(/"/g, '\\"')}"]`, `text="${view.table_name.replace(/"/g, '\\"')}"`], { timeout: 3000 });
  result.steps.push({ action: 'select_table', ...tableClick });
  await page.waitForTimeout(900);
  const viewClick = await clickExistingView(page, view.view_name);
  result.steps.push({ action: 'select_view', ...viewClick });
  await page.waitForTimeout(1200);
  result.snapshots.push(await captureSnapshot(page, outputDir, 'config_calibration_01_view_loaded'));
  await page.keyboard.press('Escape').catch(() => {});
  const filterClick = await clickToolbarButton(page, /\bFilter\b|Filter rows/, 'filter');
  result.steps.push({ action: 'open_filter_panel', ...filterClick });
  await page.waitForTimeout(1200);
  result.snapshots.push(await captureSnapshot(page, outputDir, 'config_calibration_02_filter_panel'));
  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(400);
  const sortClick = await clickToolbarButton(page, /\bSort\b|Sort rows/, 'sort');
  result.steps.push({ action: 'open_sort_panel', ...sortClick });
  await page.waitForTimeout(1200);
  result.snapshots.push(await captureSnapshot(page, outputDir, 'config_calibration_03_sort_panel'));
  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(400);
  const hideClick = await clickToolbarButton(page, /Hide fields|Fields/, 'hide-fields');
  result.steps.push({ action: 'open_hide_fields_panel', ...hideClick });
  await page.waitForTimeout(1200);
  result.snapshots.push(await captureSnapshot(page, outputDir, 'config_calibration_04_hide_fields_panel'));
  writeJson(path.join(outputDir, 'view_config_calibration_report.json'), result);
  return result;
}
