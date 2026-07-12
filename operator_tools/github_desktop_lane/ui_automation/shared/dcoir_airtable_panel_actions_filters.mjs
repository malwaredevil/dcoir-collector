import path from 'node:path';
import { safeName, nowIso, writeJson } from './dcoir_ui_common.mjs';
import {
  AIRTABLE_PANEL_READBACK_VERSION,
  captureDomEvidence,
  openAirtablePanel,
  closeOpenAirtablePanel,
  extractOpenAirtablePanel
} from './dcoir_airtable_panel_readback.mjs';
import {
  AIRTABLE_PANEL_ACTIONS_VERSION,
  exactTextPattern,
  fieldToken,
  isExpectedRelativeDateFilterRow,
  isInstructionFilterRow,
  regexEscape,
  rowText,
  summarizeFilterRowsForField
} from './dcoir_airtable_panel_actions_contract.mjs';
import {
  chooseFieldPoint,
  chooseOperatorPoint,
  chooseValuePoint,
  clickPoint
} from './dcoir_airtable_panel_actions_controls.mjs';
import { clickOptionWithDropdownScroll } from './dcoir_airtable_panel_actions_dropdown.mjs';

async function clickOptionWithTypeahead(page, pattern, query, label, bounds, steps) {
  return clickOptionWithDropdownScroll(page, pattern, query, label, bounds, steps);
}

async function extractFilterPanel(page, label, steps = null) {
  const extracted = await extractOpenAirtablePanel(page, 'filter');
  if (steps) steps.push({ action: label, ok: extracted.ok, reason: extracted.reason || null, panel: extracted.panel || null, row_count: Array.isArray(extracted.rows) ? extracted.rows.length : 0 });
  return extracted;
}

async function addFirstFilterRow(page, panel, steps) {
  const clicked = await page.evaluate(() => {
    const normalize = (s) => String(s || '').replace(/\s+/g, ' ').trim();
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    const candidates = Array.from(document.querySelectorAll('button, [role="button"], div, span'))
      .filter(visible)
      .map((el) => {
        const box = el.getBoundingClientRect();
        const text = normalize(el.innerText || el.textContent || el.getAttribute('aria-label') || '');
        return { el, text, role: el.getAttribute('role') || '', x: box.x, y: box.y, w: box.width, h: box.height };
      })
      .filter((item) => /^Add condition$/i.test(item.text) && item.x >= 250 && item.x <= 1250 && item.y >= 120 && item.y <= 500)
      .sort((a, b) => a.y - b.y || a.x - b.x);
    const chosen = candidates[0];
    if (!chosen) return { ok: false };
    chosen.el.click();
    return { ok: true, text: chosen.text, role: chosen.role, x: Math.round(chosen.x), y: Math.round(chosen.y), w: Math.round(chosen.w), h: Math.round(chosen.h) };
  });
  steps.push({ action: 'click_add_filter_condition', ...clicked });
  if (!clicked.ok) throw new Error('Could not click Add condition in filter panel.');
  await page.waitForTimeout(850).catch(() => {});
}

async function setFilterField(page, panel, row, spec, steps) {
  const point = chooseFieldPoint(row, spec.field, panel);
  await clickPoint(page, point, 'open_filter_field_control', steps);
  await page.waitForTimeout(450).catch(() => {});
  const bounds = { xMin: Math.max(250, point.x - 160), xMax: Math.min(1450, point.x + 620), yMin: Math.max(80, point.y - 80), yMax: Math.min(900, point.y + 620) };
  const option = await clickOptionWithTypeahead(page, exactTextPattern(spec.field), spec.field, 'select_filter_field', bounds, steps);
  if (!option.ok) throw new Error(`Could not select filter field ${spec.field}.`);
}

async function setFilterOperator(page, panel, row, spec, steps) {
  const point = chooseOperatorPoint(row, panel);
  await clickPoint(page, point, 'open_filter_operator_control', steps);
  await page.waitForTimeout(450).catch(() => {});
  const desired = String(spec.operator || '').trim().replace(/^is\s+/i, '');
  const patterns = [];
  if (/on or before/i.test(desired)) patterns.push(/^is\s+on\s+or\s+before(\.{3}|…)?$/i, /^on\s+or\s+before(\.{3}|…)?$/i);
  else patterns.push(new RegExp(`^${regexEscape(desired)}(\\.{3}|…)?$`, 'i'));
  const bounds = { xMin: Math.max(250, point.x - 220), xMax: Math.min(1450, point.x + 560), yMin: Math.max(80, point.y - 80), yMax: Math.min(900, point.y + 620) };
  for (const pattern of patterns) {
    const option = await clickOptionWithTypeahead(page, pattern, `is ${desired}`, 'select_filter_operator', bounds, steps);
    if (option.ok) return;
  }
  throw new Error(`Could not select filter operator ${spec.operator}.`);
}

async function setRelativeDateValue(page, panel, row, spec, steps) {
  const point = chooseValuePoint(row, panel);
  await clickPoint(page, point, 'open_relative_date_value_control', steps);
  await page.waitForTimeout(500).catch(() => {});
  const bounds = { xMin: Math.max(250, point.x - 180), xMax: Math.min(1450, point.x + 620), yMin: Math.max(80, point.y - 120), yMax: Math.min(900, point.y + 620) };
  const value = String(spec.value || '').trim();
  const option = await clickOptionWithTypeahead(page, exactTextPattern(value), value, 'select_relative_date_value', bounds, steps);
  if (!option.ok) throw new Error(`Could not select relative date value ${value}.`);
}

function chooseSingleFilterRow(panelState, spec) {
  const rowsForField = summarizeFilterRowsForField(panelState, spec.field);
  if (rowsForField.length === 0) return null;
  if (rowsForField.length > 1) {
    throw new Error(`Refusing to normalize filter: found ${rowsForField.length} ${spec.field} rows.`);
  }
  return rowsForField[0];
}

export async function ensureSingleRelativeDateFilter(page, options = {}) {
  const spec = {
    field: options.field,
    operator: options.operator,
    value: options.value
  };
  if (!spec.field || !spec.operator || !spec.value) throw new Error('ensureSingleRelativeDateFilter requires field, operator, and value.');
  const outputDir = options.outputDir || process.cwd();
  const evidenceLabel = options.evidenceLabel || `${spec.field}_${spec.operator}_${spec.value}`;
  const screenshotOptions = options.screenshotOptions || {};
  const steps = [];
  const snapshots = [];

  const opened = await openAirtablePanel(page, 'filter');
  await page.waitForTimeout(600).catch(() => {});
  steps.push({ action: 'open_filter_panel', opened });
  let panelState = await extractFilterPanel(page, 'extract_filter_panel_initial', steps);
  let row = chooseSingleFilterRow(panelState, spec);

  if (row && isExpectedRelativeDateFilterRow(row, spec)) {
    await closeOpenAirtablePanel(page).catch(() => {});
    return { status: 'already_correct', steps, snapshots };
  }

  if (!row) {
    await addFirstFilterRow(page, panelState.panel, steps);
    snapshots.push(await captureDomEvidence(page, outputDir, `${safeName(evidenceLabel)}_filter_row_added`, screenshotOptions));
    panelState = await extractFilterPanel(page, 'extract_filter_panel_after_add', steps);
    row = chooseSingleFilterRow(panelState, spec) || (Array.isArray(panelState.rows) ? panelState.rows.find((candidate) => !isInstructionFilterRow(candidate)) : null);
    if (!row) throw new Error('Could not find a filter row after Add condition.');
  }

  const currentText = rowText(row);
  if (!currentText.includes(fieldToken(spec.field))) {
    await setFilterField(page, panelState.panel, row, spec, steps);
    await page.waitForTimeout(850).catch(() => {});
    panelState = await extractFilterPanel(page, 'extract_filter_panel_after_field', steps);
    row = chooseSingleFilterRow(panelState, spec);
    if (!row) throw new Error(`Could not verify filter field ${spec.field} after selection.`);
  }

  if (!isExpectedRelativeDateFilterRow(row, { ...spec, value: '' })) {
    await setFilterOperator(page, panelState.panel, row, spec, steps);
    await page.waitForTimeout(1000).catch(() => {});
    panelState = await extractFilterPanel(page, 'extract_filter_panel_after_operator', steps);
    row = chooseSingleFilterRow(panelState, spec);
    if (!row) throw new Error(`Could not verify filter row for ${spec.field} after operator selection.`);
  }

  if (!isExpectedRelativeDateFilterRow(row, spec)) {
    await setRelativeDateValue(page, panelState.panel, row, spec, steps);
    await page.waitForTimeout(1000).catch(() => {});
    panelState = await extractFilterPanel(page, 'extract_filter_panel_after_value', steps);
    row = chooseSingleFilterRow(panelState, spec);
  }

  snapshots.push(await captureDomEvidence(page, outputDir, `${safeName(evidenceLabel)}_filter_normalized`, screenshotOptions));
  const verified = row && isExpectedRelativeDateFilterRow(row, spec);
  const report = {
    timestamp_utc: nowIso(),
    shared_panel_actions_version: AIRTABLE_PANEL_ACTIONS_VERSION,
    shared_panel_readback_version: AIRTABLE_PANEL_READBACK_VERSION,
    status: verified ? 'relative_date_filter_verified' : 'relative_date_filter_gap_after_actions',
    spec,
    final_row: row ? { text: row.text || '', normalized_text: rowText(row), y: row.y, cells: row.cells || {} } : null,
    steps,
    snapshots
  };
  writeJson(path.join(outputDir, `${safeName(evidenceLabel)}_panel_action_report.json`), report);
  await closeOpenAirtablePanel(page).catch(() => {});
  if (!verified) throw new Error(`Relative date filter action failed to verify ${spec.field} ${spec.operator} ${spec.value}.`);
  return report;
}
