import { lowerText } from './airtable_wbs09_apply_validation_due_view_contract.mjs';

export function relevantFilterRows(state) {
  return (Array.isArray(state?.rows) ? state.rows : []).filter((row) => {
    const text = lowerText(`${row.text || ''} ${Object.values(row.cells || {}).join(' ')}`);
    if (!text) return false;
    if (/no filter conditions are applied|add condition|learn more about filtering/.test(text)) return false;
    return /where|review_after| is |before|after|today/.test(text);
  });
}

export function relevantSortRows(state) {
  return (Array.isArray(state?.rows) ? state.rows : []).filter((row) => {
    const text = lowerText(`${row.text || ''} ${Object.values(row.cells || {}).join(' ')}`);
    if (!text) return false;
    if (/add another sort|find a field|copy from another view|sort by/.test(text) && !/review_after/.test(text)) return false;
    return /review_after/.test(text) && /earliest\s*->\s*latest|latest\s*->\s*earliest|ascending|descending|a\s*->\s*z|z\s*->\s*a|1\s*->\s*9|9\s*->\s*1/.test(text);
  });
}

export function sortDirectionObservedForField(rows, expectedSort) {
  const field = lowerText(expectedSort?.field || '');
  if (!field) return false;
  const wanted = String(expectedSort?.direction || '').toLowerCase() === 'desc' ? 'desc' : 'asc';
  for (const row of rows || []) {
    const text = lowerText(`${row.text || ''} ${Object.values(row.cells || {}).join(' ')}`);
    if (!text.includes(field)) continue;
    const hasAsc = /a\s*->\s*z|1\s*->\s*9|earliest\s*->\s*latest|ascending/.test(text);
    const hasDesc = /z\s*->\s*a|9\s*->\s*1|latest\s*->\s*earliest|descending/.test(text);
    if (wanted === 'desc' && hasDesc) return true;
    if (wanted === 'asc' && hasAsc) return true;
  }
  return false;
}

export function stripReadbackPhasePrefix(message) {
  return String(message || '')
    .replace(/^(before_refresh|after_refresh|before_apply|after_apply|after_click|after_filter_click):\s*/i, '')
    .trim();
}

export function expectedReviewAfterTodayFilter(plan) {
  const filters = plan?.expected?.filters || plan?.target?.expected_filters || [];
  return Array.isArray(filters) && filters.length === 1
    && String(filters[0]?.field || '') === 'review_after'
    && String(filters[0]?.operator || '').toLowerCase() === 'on or before'
    && String(filters[0]?.value || '').toLowerCase() === 'today';
}

export function expectedReviewAfterAscendingSort(plan) {
  const sorts = plan?.expected?.sorts || plan?.target?.expected_sorts || [];
  return Array.isArray(sorts) && sorts.length === 1
    && String(sorts[0]?.field || '') === 'review_after'
    && String(sorts[0]?.direction || '').toLowerCase() === 'asc';
}

export function collectPlanMissing(plan, before) {
  const values = [];
  for (const v of plan?.comparison?.missing_unique || []) values.push(v);
  for (const v of plan?.comparison?.missing_raw || []) values.push(v);
  for (const v of before?.comparison?.missing || []) values.push(v);
  return Array.from(new Set(values.map(stripReadbackPhasePrefix).filter(Boolean)));
}

export function summarizePlanSafety(plan, before) {
  const filterRows = relevantFilterRows(before.filter);
  const sortRows = relevantSortRows(before.sort);
  const planned = plan?.planned_actions || {};
  const originalFilterAction = planned.filter_action || null;
  const originalSortAction = planned.sort_action || null;
  const missing = collectPlanMissing(plan, before);
  const filterMissing = missing.some((message) => /filter row not observed/i.test(message) || (/\bfilter\b/i.test(message) && /review_after/i.test(message)));
  const sortMissing = missing.some((message) => /sort row not observed|sort panel extraction failed/i.test(message) || (/\bsort\b/i.test(message) && /review_after/i.test(message)));

  let filterAction = originalFilterAction;
  let sortAction = originalSortAction;

  // Purpose-specific safety: allow only a missing first review_after/today row,
  // or one existing review_after row that can be normalized to the exact contract.
  if (filterRows.length === 0 && expectedReviewAfterTodayFilter(plan) && filterMissing && originalFilterAction === 'replace_or_normalize_filters') {
    filterAction = 'add_or_build_filters';
  }
  if (filterRows.length === 1 && expectedReviewAfterTodayFilter(plan) && filterMissing && originalFilterAction === 'replace_or_normalize_filters') {
    const onlyFilterText = lowerText(filterRows[0]?.text || '');
    if (/review_after/.test(onlyFilterText) && !(/on or before/.test(onlyFilterText) && /today/.test(onlyFilterText))) {
      filterAction = 'normalize_single_relative_date_filter';
    }
  }

  // Treat an empty/failed sort panel readback as the safe add-first-sort case
  // only for the exact supported review_after ascending contract.
  if (sortRows.length === 0 && expectedReviewAfterAscendingSort(plan) && sortMissing && originalSortAction === 'replace_or_normalize_sorts') {
    sortAction = 'add_or_build_sorts';
  }

  const filterAllowed = filterAction === 'noop'
    || (filterAction === 'add_or_build_filters' && filterRows.length === 0)
    || (filterAction === 'normalize_single_relative_date_filter' && filterRows.length === 1);
  const sortAllowed = sortAction === 'noop' || (sortAction === 'add_or_build_sorts' && sortRows.length === 0);
  return {
    original_filter_action: originalFilterAction,
    original_sort_action: originalSortAction,
    filter_action: filterAction,
    sort_action: sortAction,
    filter_rows_observed: filterRows.length,
    sort_rows_observed: sortRows.length,
    missing,
    filter_missing: filterMissing,
    sort_missing: sortMissing,
    filter_allowed: filterAllowed,
    sort_allowed: sortAllowed,
    allowed: filterAllowed && sortAllowed,
    hard_stop_reason: filterAllowed && sortAllowed ? null : 'This helper only adds missing first filter/sort rows or no-ops when already correct; it will not replace/delete/normalize existing rows.'
  };
}
