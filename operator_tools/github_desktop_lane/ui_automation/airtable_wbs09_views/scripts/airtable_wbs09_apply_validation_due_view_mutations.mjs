import { nowIso, safeName } from '../../shared/dcoir_ui_common.mjs';
import {
  AIRTABLE_PANEL_READBACK_VERSION,
  selectAirtableTableAndView,
  captureDomEvidence,
  captureAirtablePanelState,
  compareAirtablePanelReadback,
  openAirtablePanel,
  closeOpenAirtablePanel,
  extractOpenAirtablePanel
} from '../../shared/dcoir_airtable_panel_readback.mjs';
import {
  AIRTABLE_PANEL_DISCOVERY_VERSION,
  buildAirtableViewChangePlan,
  captureAirtablePanelDiscovery
} from '../../shared/dcoir_airtable_panel_discovery.mjs';
import {
  AIRTABLE_PANEL_ACTIONS_VERSION,
  ensureSingleRelativeDateFilter
} from '../../shared/dcoir_airtable_panel_actions.mjs';
import {
  REQUIRED_TOKEN,
  SUPPORTED_TARGET_KEY,
  TOOL_VERSION,
  assertSupportedTarget,
  exactTextPattern
} from './airtable_wbs09_apply_validation_due_view_contract.mjs';
import {
  relevantFilterRows,
  relevantSortRows,
  sortDirectionObservedForField,
  summarizePlanSafety
} from './airtable_wbs09_apply_validation_due_view_safety.mjs';
import {
  clickAt,
  clickOpenOptionExact,
  clickVisibleText,
  keyboardSelectAt,
  pointFromPanel,
  rowYFromExtraction
} from './airtable_wbs09_apply_validation_due_view_clicks.mjs';

export {
  AIRTABLE_PANEL_ACTIONS_VERSION,
  AIRTABLE_PANEL_DISCOVERY_VERSION,
  AIRTABLE_PANEL_READBACK_VERSION
};

export async function verifyTarget(runtime, target, phase) {
  const { page, outputDir, args } = runtime;
  const filter = await captureAirtablePanelState(page, outputDir, target, 'filter', phase, args);
  const sort = await captureAirtablePanelState(page, outputDir, target, 'sort', phase, args);
  const comparison = compareAirtablePanelReadback({ target, before_filter: filter, after_filter: filter, before_sort: sort, after_sort: sort });
  return { filter, sort, comparison };
}

export async function openPanelAndExtract(page, kind) {
  const opened = await openAirtablePanel(page, kind);
  await page.waitForTimeout(500);
  const extracted = await extractOpenAirtablePanel(page, kind);
  return { opened, extracted };
}

export async function addReviewAfterFilter(runtime, target, result) {
  const { page, outputDir, args } = runtime;
  const expectedFilter = target.expected_filters[0];
  const opened = await openPanelAndExtract(page, 'filter');
  result.steps.push({ action: 'open_filter_panel_for_mutation', opened: opened.opened, panel_extraction: { ok: opened.extracted.ok, reason: opened.extracted.reason || null, panel: opened.extracted.panel || null } });

  const beforeRows = relevantFilterRows({ rows: opened.extracted.rows || [], panel_extraction: { ok: opened.extracted.ok } });
  if (beforeRows.length > 0) {
    throw new Error('Filter mutation refused: existing filter-like rows are present. This helper only adds a missing first filter row.');
  }

  const add = await clickVisibleText(page, /^Add condition$/i, 'filter-add-condition', { xMin: 450, xMax: 1120, yMin: 160, yMax: 420 });
  result.steps.push({ action: 'click_add_filter_condition', ...add });
  if (!add.ok) throw new Error('Could not click Add condition in filter panel.');
  await page.waitForTimeout(900);
  result.snapshots.push(await captureDomEvidence(page, outputDir, `${safeName(target.table_name)}_${safeName(target.view_name)}_filter_condition_added`, args));

  const afterAdd = await extractOpenAirtablePanel(page, 'filter');
  const panel = afterAdd.panel || opened.extracted.panel || { x: 521, y: 129 };
  const rowY = rowYFromExtraction(afterAdd, (panel.y || 129) + 138);
  result.steps.push({ action: 'filter_after_add_extraction', ok: afterAdd.ok, reason: afterAdd.reason || null, panel: afterAdd.panel || null, row_y: rowY });

  const fieldPoint = pointFromPanel(panel, 151, rowY);
  const field = await keyboardSelectAt(page, fieldPoint, expectedFilter.field, 'filter-field-review_after');
  result.steps.push({ action: 'set_filter_field', field: expectedFilter.field, ...field });

  const operatorPoint = pointFromPanel(panel, 276, rowY);
  const operator = await keyboardSelectAt(page, operatorPoint, 'is on or before', 'filter-operator-is-on-or-before');
  result.steps.push({ action: 'set_filter_operator', operator: 'is on or before', ...operator });

  await page.waitForTimeout(700);
  const maybeDefault = await extractOpenAirtablePanel(page, 'filter');
  const maybeState = { panel_extraction: { ok: maybeDefault.ok }, rows: maybeDefault.rows || [] };
  const alreadyToday = relevantFilterRows(maybeState).some((row) => /review_after/i.test(row.text || '') && /on or before/i.test(row.text || '') && /today/i.test(row.text || ''));
  result.steps.push({ action: 'relative_date_value_default_probe', already_today: alreadyToday });
  if (!alreadyToday) {
    const valuePanel = maybeDefault.panel || panel;
    const valueY = rowYFromExtraction(maybeDefault, rowY);
    const valuePoint = pointFromPanel(valuePanel, 443, valueY);
    const openValue = await clickAt(page, valuePoint, 'filter-relative-date-value-open');
    await page.waitForTimeout(500);
    const today = await clickOpenOptionExact(page, 'today', 'filter-relative-date-today-option', {
      xMin: Math.max(250, valuePoint.x - 120),
      xMax: Math.min(1450, valuePoint.x + 550),
      yMin: Math.max(90, valuePoint.y - 60),
      yMax: Math.min(900, valuePoint.y + 540)
    });
    result.steps.push({ action: 'set_filter_relative_date_value', value: 'today', open: openValue, option: today });
  }

  await page.waitForTimeout(1000);
  result.snapshots.push(await captureDomEvidence(page, outputDir, `${safeName(target.table_name)}_${safeName(target.view_name)}_filter_configured`, args));
  await closeOpenAirtablePanel(page);
}

export async function addReviewAfterSort(runtime, target, result) {
  const { page, outputDir, args } = runtime;
  const expectedSort = target.expected_sorts[0];
  const opened = await openPanelAndExtract(page, 'sort');
  result.steps.push({ action: 'open_sort_panel_for_mutation', opened: opened.opened, panel_extraction: { ok: opened.extracted.ok, reason: opened.extracted.reason || null, panel: opened.extracted.panel || null } });

  const existingSortRows = relevantSortRows({ rows: opened.extracted.rows || [], panel_extraction: { ok: opened.extracted.ok } });
  if (existingSortRows.length > 0) {
    if (sortDirectionObservedForField(existingSortRows, expectedSort)) {
      result.steps.push({ action: 'sort_already_present', ok: true, rows: existingSortRows.map((row) => row.text) });
      await closeOpenAirtablePanel(page);
      return;
    }
    throw new Error('Sort mutation refused: existing sort-like rows are present but not the expected review_after ascending row. This helper will not replace/normalize sorts.');
  }

  let fieldClick = await clickVisibleText(page, exactTextPattern(expectedSort.field), 'sort-field-review_after-direct', { xMin: 760, xMax: 1260, yMin: 130, yMax: 820 });
  if (!fieldClick.ok) {
    const panel = opened.extracted.panel || { x: 891, y: 130 };
    const searchPoint = { x: panel.x + 28, y: panel.y + 64 };
    await clickAt(page, searchPoint, 'sort-field-search-open');
    await page.waitForTimeout(250);
    await page.keyboard.type(expectedSort.field, { delay: 15 });
    await page.waitForTimeout(700);
    fieldClick = await clickVisibleText(page, exactTextPattern(expectedSort.field), 'sort-field-review_after-after-search', { xMin: 760, xMax: 1260, yMin: 130, yMax: 820 });
    if (!fieldClick.ok) {
      await page.keyboard.press('Enter');
      fieldClick = { ok: true, selector: 'keyboard-enter:sort-field-review_after-after-search', value: expectedSort.field };
    }
  }
  result.steps.push({ action: 'set_sort_field', field: expectedSort.field, ...fieldClick });
  await page.waitForTimeout(1200);
  result.snapshots.push(await captureDomEvidence(page, outputDir, `${safeName(target.table_name)}_${safeName(target.view_name)}_sort_field_selected`, args));

  const postField = await extractOpenAirtablePanel(page, 'sort');
  const postRows = relevantSortRows({ rows: postField.rows || [], panel_extraction: { ok: postField.ok } });
  const directionOk = sortDirectionObservedForField(postRows, expectedSort);
  result.steps.push({ action: 'sort_direction_after_field_select_probe', direction_ok: directionOk, rows: postRows.map((row) => row.text), panel_extraction: { ok: postField.ok, reason: postField.reason || null, panel: postField.panel || null } });

  if (!directionOk) {
    const panel = postField.panel || opened.extracted.panel;
    if (!panel) throw new Error('Cannot set sort direction: no sort panel geometry after field select.');
    const rowY = rowYFromExtraction(postField, panel.y + 70);
    const directionPoint = { x: panel.x + Math.min(333, Math.max(260, panel.w - 120)), y: rowY };
    await clickAt(page, directionPoint, 'sort-direction-open');
    await page.waitForTimeout(500);
    const option = await clickVisibleText(page, /^(Earliest\s*->\s*Latest|A\s*->\s*Z|1\s*->\s*9|Ascending)$/i, 'sort-direction-earliest-latest', {
      xMin: Math.max(250, directionPoint.x - 150),
      xMax: Math.min(1450, directionPoint.x + 400),
      yMin: Math.max(90, directionPoint.y - 80),
      yMax: Math.min(900, directionPoint.y + 420)
    });
    result.steps.push({ action: 'set_sort_direction_ascending', option });
    if (!option.ok) throw new Error('Could not click ascending sort direction option.');
  }

  await page.waitForTimeout(900);
  result.snapshots.push(await captureDomEvidence(page, outputDir, `${safeName(target.table_name)}_${safeName(target.view_name)}_sort_configured`, args));
  await closeOpenAirtablePanel(page);
}

export async function applyOneTarget(runtime, target) {
  const { page, outputDir, args, log } = runtime;
  assertSupportedTarget(target);
  const result = {
    timestamp_utc: nowIso(),
    tool_version: TOOL_VERSION,
    shared_panel_readback_version: AIRTABLE_PANEL_READBACK_VERSION,
    shared_panel_discovery_version: AIRTABLE_PANEL_DISCOVERY_VERSION,
    shared_panel_actions_version: AIRTABLE_PANEL_ACTIONS_VERSION,
    target,
    status: 'started',
    safety: {
      one_view_only: true,
      supported_target_key: SUPPORTED_TARGET_KEY,
      supported_mutation: 'add missing first review_after on-or-before today filter, normalize one existing review_after exact-date/unset filter, and add missing first sort review_after ascending only',
      disallowed_mutations: ['create_view', 'delete_view', 'delete_filter', 'delete_sort', 'replace_unrelated_filter', 'replace_existing_sort', 'multi_filter', 'multi_sort', 'non_review_after_field'],
      exact_token_required: REQUIRED_TOKEN
    },
    steps: [],
    snapshots: []
  };

  log('Validation-due view apply target starting.', { table_name: target.table_name, view_name: target.view_name });
  result.steps.push(await selectAirtableTableAndView(page, target));
  result.snapshots.push(await captureDomEvidence(page, outputDir, `${safeName(target.table_name)}_${safeName(target.view_name)}_00_target_loaded`, args));

  result.before = await verifyTarget(runtime, target, 'before_apply');
  if (result.before.comparison.ok) {
    result.status = 'already_correct_noop';
    result.completed_at_utc = nowIso();
    return result;
  }

  result.plan = buildAirtableViewChangePlan(target, result.before.filter, result.before.sort);
  result.pre_execute_gate = summarizePlanSafety(result.plan, result.before);
  if (!result.pre_execute_gate.allowed) {
    throw new Error(`Pre-execute safety gate failed: ${JSON.stringify(result.pre_execute_gate)}`);
  }

  result.discovery_before_filter = await captureAirtablePanelDiscovery(page, outputDir, target, 'filter', 'pre_execute', {
    ...args,
    probeDropdownOptions: false,
    maxDropdownProbes: 0
  });
  result.discovery_before_sort = await captureAirtablePanelDiscovery(page, outputDir, target, 'sort', 'pre_execute', {
    ...args,
    probeDropdownOptions: false,
    maxDropdownProbes: 0
  });

  if (['add_or_build_filters', 'normalize_single_relative_date_filter'].includes(result.pre_execute_gate.filter_action)) {
    const filterAction = await ensureSingleRelativeDateFilter(page, {
      field: 'review_after',
      operator: 'on or before',
      value: 'today',
      outputDir,
      evidenceLabel: `${safeName(target.table_name)}_${safeName(target.view_name)}_review_after_on_or_before_today`,
      screenshotOptions: args
    });
    result.steps.push({ action: 'shared_ensure_single_relative_date_filter', status: filterAction.status, report: filterAction });
    result.snapshots.push(...(filterAction.snapshots || []));
    result.mutation_attempted = true;
    result.mutation_types = [...(result.mutation_types || []), result.pre_execute_gate.filter_action === 'add_or_build_filters' ? 'add_filter_review_after_on_or_before_today' : 'normalize_filter_review_after_on_or_before_today'];
  }

  result.after_filter_click = await verifyTarget(runtime, target, 'after_filter_click');

  if (result.pre_execute_gate.sort_action === 'add_or_build_sorts') {
    await addReviewAfterSort(runtime, target, result);
    result.mutation_attempted = true;
    result.mutation_types = [...(result.mutation_types || []), 'add_sort_review_after_ascending'];
  }

  result.after_click = await verifyTarget(runtime, target, 'after_click');
  if (!result.after_click.comparison.ok) {
    throw new Error(`After-click verification failed: ${JSON.stringify(result.after_click.comparison.missing || [])}`);
  }

  await page.reload({ waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(1200);
  result.after_reload_select = await selectAirtableTableAndView(page, target);
  result.after_refresh = await verifyTarget(runtime, target, 'after_refresh');
  result.status = result.after_refresh.comparison.ok ? 'validation_due_view_verified_after_refresh' : 'validation_due_view_gap_after_refresh';
  result.completed_at_utc = nowIso();
  return result;
}
