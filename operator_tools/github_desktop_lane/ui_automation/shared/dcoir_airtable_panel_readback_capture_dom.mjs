import path from 'node:path';
import { writeJson, safeName, nowIso } from './dcoir_ui_common.mjs';
import { AIRTABLE_UI_GEOMETRY_VERSION } from './dcoir_airtable_ui_geometry.mjs';
import { AIRTABLE_PANEL_READBACK_VERSION } from './dcoir_airtable_panel_readback_contract.mjs';

export async function getVisibleElements(page, options = {}) {
  const limit = options.limit || 6000;
  return await page.evaluate((limit) => {
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    function panelPriority(item) {
      const content = String(`${item.text} ${item.aria} ${item.placeholder} ${item.value}`).toLowerCase();
      const inPanelBand = item.x >= 250 && item.x <= 1250 && item.y >= 70 && item.y <= 760 && item.w <= 1000 && item.h <= 760;
      const hasPanelSignal = /sort by|add another sort|automatically sort records|filter|in this view, show records|add condition|copy from another view|enter a date|gmt/.test(content);
      return inPanelBand && hasPanelSignal ? 0 : 1;
    }
    return Array.from(document.querySelectorAll('button, [role="button"], input, textarea, [aria-label], [placeholder], [contenteditable="true"], div, span, a'))
      .slice(0, limit)
      .map((el) => {
        const box = el.getBoundingClientRect();
        return {
          tag: el.tagName,
          role: el.getAttribute('role') || '',
          aria: el.getAttribute('aria-label') || '',
          placeholder: el.getAttribute('placeholder') || '',
          type: el.getAttribute('type') || '',
          value: String(el.value || '').replace(/\s+/g, ' ').trim().slice(0, 500),
          text: (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 500),
          x: Math.round(box.x),
          y: Math.round(box.y),
          w: Math.round(box.width),
          h: Math.round(box.height),
          visible: visible(el)
        };
      })
      .filter((item) => item.visible && (item.text || item.aria || item.placeholder || item.role || item.type || item.value))
      .sort((a, b) => panelPriority(a) - panelPriority(b) || a.y - b.y || a.x - b.x || (a.w * a.h) - (b.w * b.h))
      .slice(0, 1600);
  }, limit);
}

export async function captureAirtableGridRowState(page, outputDir, target, phase = 'target_loaded') {
  const rowState = await page.evaluate(() => {
    const normalize = (s) => String(s || '').replace(/[\u2192\u27f6\u2794]/g, ' -> ').replace(/\s+/g, ' ').trim();
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    function itemFor(el) {
      const box = el.getBoundingClientRect();
      return {
        tag: el.tagName,
        role: el.getAttribute('role') || '',
        testid: el.getAttribute('data-testid') || '',
        aria: normalize(el.getAttribute('aria-label') || ''),
        text: normalize(el.innerText || el.textContent || ''),
        x: Math.round(box.x),
        y: Math.round(box.y),
        w: Math.round(box.width),
        h: Math.round(box.height)
      };
    }
    const bodyText = normalize(document.body ? document.body.innerText : '').toLowerCase();
    const noRecordsSignal = /\b(no records|no records in this view|there are no records|0 records)\b/i.test(bodyText);
    const gridCells = Array.from(document.querySelectorAll('[role="gridcell"], [data-testid*="cell"], [data-testid*="gridCell"], [data-testid*="recordCell"]'))
      .filter(visible)
      .map(itemFor)
      .filter((item) => item.y > 165 && item.w > 8 && item.h > 8 && item.x > 220)
      .slice(0, 80);
    const gridRows = Array.from(document.querySelectorAll('[role="row"], [data-testid*="row"], [data-rowindex]'))
      .filter(visible)
      .map(itemFor)
      .filter((item) => item.y > 165 && item.w > 80 && item.h > 12)
      .slice(0, 80);
    const rowHeaderSignals = Array.from(document.querySelectorAll('[aria-label*="record" i], [data-testid*="record" i], button, div, span'))
      .filter(visible)
      .map(itemFor)
      .filter((item) => item.y > 165 && item.x >= 0 && item.x < 360 && /record|row/i.test(`${item.aria} ${item.testid} ${item.text}`))
      .slice(0, 40);
    let state = 'unknown';
    if (noRecordsSignal) state = 'none';
    else if (gridCells.length > 0 || gridRows.length > 1 || rowHeaderSignals.length > 0) state = 'visible';
    return {
      ok: true,
      row_state: state,
      no_records_signal: noRecordsSignal,
      visible_grid_cell_count: gridCells.length,
      visible_grid_row_count: gridRows.length,
      row_header_signal_count: rowHeaderSignals.length,
      grid_cell_samples: gridCells.slice(0, 10),
      grid_row_samples: gridRows.slice(0, 10),
      row_header_signal_samples: rowHeaderSignals.slice(0, 10)
    };
  }).catch((error) => ({ ok: false, row_state: 'unknown', error: String(error?.message || error) }));
  const payload = {
    timestamp_utc: nowIso(),
    tool_version: AIRTABLE_PANEL_READBACK_VERSION,
    geometry_version: AIRTABLE_UI_GEOMETRY_VERSION,
    target,
    phase,
    ...rowState
  };
  const statePath = path.join(outputDir, `${safeName(target.table_name)}_${safeName(target.view_name)}_${phase}_row_state.json`);
  writeJson(statePath, payload);
  return { ...payload, state_path: statePath };
}

export async function captureDomEvidence(page, outputDir, label, options = {}) {
  const payload = {
    timestamp_utc: nowIso(),
    tool_version: AIRTABLE_PANEL_READBACK_VERSION,
    geometry_version: AIRTABLE_UI_GEOMETRY_VERSION,
    label,
    url: page.url(),
    title: await page.title(),
    elements: await getVisibleElements(page)
  };
  const domPath = path.join(outputDir, `${safeName(label)}.dom.json`);
  writeJson(domPath, payload);
  const result = { label, dom_evidence: domPath };
  if (options.enableScreenshots) {
    const screenshotPath = path.join(outputDir, `${safeName(label)}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true });
    result.screenshot = screenshotPath;
  }
  return result;
}
