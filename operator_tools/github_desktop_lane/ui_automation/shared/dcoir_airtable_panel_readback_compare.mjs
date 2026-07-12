import {
  filterReadbackTargetsForResume,
  reloadPageWithRetry,
  targetKeyOfReadbackTarget
} from './dcoir_airtable_panel_readback_targets.mjs';

function normalizeText(s) {
  return String(s || '')
    .replace(/[\u2192\u27f6\u2794]/g, ' -> ')
    .replace(/\s+/g, ' ')
    .trim();
}

function lowerText(s) {
  return normalizeText(s).toLowerCase();
}

function uniqueNonEmpty(parts) {
  const out = [];
  for (const part of parts.map(normalizeText).filter(Boolean)) {
    if (!out.some((existing) => existing.toLowerCase() === part.toLowerCase())) out.push(part);
  }
  return out;
}

function includesWholePhrase(text, phrase) {
  const haystack = lowerText(text);
  const needle = lowerText(phrase);
  if (!needle) return true;
  if (needle.includes(' ')) return haystack.includes(needle);
  return new RegExp(`(^|[^a-z0-9_])${needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}([^a-z0-9_]|$)`, 'i').test(haystack);
}

function operatorLabels(operator) {
  const op = lowerText(operator);
  if (op === '=') return ['is', '='];
  if (op === 'is one of') return ['is any of', 'is one of'];
  if (op === 'is not empty') return ['is not empty'];
  if (op === 'contains') return ['contains'];
  if (op === 'on or before') return ['is on or before', 'on or before'];
  return [op];
}

function filterNeedsValue(filter) {
  return filter && lowerText(filter.operator) !== 'is not empty';
}

function rowMatchesField(row, fieldName) {
  const fieldText = row?.cells?.field_text || '';
  if (includesWholePhrase(fieldText, fieldName)) return true;
  const exactFieldElement = (row.elements || []).some((el) => {
    const content = lowerText(`${el.text} ${el.aria} ${el.placeholder} ${el.value}`);
    const isLeftSide = el.cx <= (Math.min(...(row.elements || []).map((e) => e.cx)) + 360);
    return isLeftSide && lowerText(fieldName) === content;
  });
  return exactFieldElement;
}

function rowMatchesOperator(row, operator) {
  const text = `${row?.cells?.operator_text || ''} | ${row?.text || ''}`;
  return operatorLabels(operator).some((label) => includesWholePhrase(text, label));
}

function rowMatchesBooleanValue(row, value) {
  const text = `${row?.cells?.operator_text || ''} | ${row?.cells?.value_text || ''} | ${row?.text || ''}`;
  if (value === true) return /\b(is checked|checked|true|yes)\b/i.test(text);
  return /\b(is unchecked|unchecked|false|no)\b/i.test(text);
}

function rowMatchesScalarValue(row, value) {
  if (typeof value === 'boolean') return rowMatchesBooleanValue(row, value);
  const valueText = `${row?.cells?.value_text || ''} | ${row?.text || ''}`;
  const wanted = String(value);
  if (lowerText(wanted) === 'today') return includesWholePhrase(valueText, 'today');
  return includesWholePhrase(valueText, wanted);
}

function rowMatchesFilterValue(row, filter) {
  if (!filterNeedsValue(filter)) return true;
  const value = filter.value;
  if (value === null || typeof value === 'undefined') return false;
  if (Array.isArray(value)) return value.every((item) => rowMatchesScalarValue(row, item));
  return rowMatchesScalarValue(row, value);
}

function rowMatchesFilter(row, filter) {
  return rowMatchesField(row, filter.field) && rowMatchesOperator(row, filter.operator) && rowMatchesFilterValue(row, filter);
}

function sortDirectionLabels(direction) {
  const dir = lowerText(direction);
  if (dir === 'asc' || dir === 'ascending') return ['ascending', 'a -> z', '1 -> 9', 'a to z', '1 to 9', 'first -> last', 'earliest -> latest'];
  if (dir === 'desc' || dir === 'descending') return ['descending', 'z -> a', '9 -> 1', 'z to a', '9 to 1', 'last -> first', 'latest -> earliest'];
  return [dir];
}

function rowMatchesSortDirection(row, direction) {
  const text = `${row?.cells?.direction_text || ''} | ${row?.text || ''}`;
  return sortDirectionLabels(direction).some((label) => includesWholePhrase(text, label));
}

function rowMatchesSort(row, sort) {
  return rowMatchesField(row, sort.field) && rowMatchesSortDirection(row, sort.direction);
}

function compareFiltersForState(state, expectedFilters, phaseLabel) {
  const missing = [];
  if (!state?.panel_extraction?.ok) {
    missing.push(`${phaseLabel}: filter panel extraction failed`);
    return missing;
  }
  const rows = Array.isArray(state.rows) ? state.rows : [];
  if (expectedFilters.length === 0) return missing;
  for (const filter of expectedFilters) {
    const matched = rows.some((row) => rowMatchesFilter(row, filter));
    if (!matched) {
      const value = Array.isArray(filter.value) ? filter.value.join(',') : String(filter.value);
      missing.push(`${phaseLabel}: filter row not observed: field=${filter.field}; operator=${filter.operator}; value=${value}`);
    }
  }
  return missing;
}

function rowLooksLikeSortCondition(row) {
  const cells = row?.cells || {};
  const text = `${cells.field_text || ''} | ${cells.direction_text || ''} | ${row?.text || ''}`;
  if (!cells.field_text || !cells.direction_text) return false;
  if (/add another sort|add sort/i.test(cells.field_text)) return false;
  return /a\s*->\s*z|z\s*->\s*a|1\s*->\s*9|9\s*->\s*1|first\s*->\s*last|last\s*->\s*first|earliest\s*->\s*latest|latest\s*->\s*earliest|ascending|descending/i.test(text);
}

function orderedSortRows(state) {
  return (Array.isArray(state?.rows) ? state.rows : [])
    .filter(rowLooksLikeSortCondition)
    .sort((a, b) => (a.y || 0) - (b.y || 0));
}

function compareSortsForState(state, expectedSorts, phaseLabel) {
  const missing = [];
  if (!state?.panel_extraction?.ok) {
    missing.push(`${phaseLabel}: sort panel extraction failed`);
    return missing;
  }
  const rows = orderedSortRows(state);
  for (let i = 0; i < expectedSorts.length; i += 1) {
    const sort = expectedSorts[i];
    const row = rows[i];
    if (!row || !rowMatchesSort(row, sort)) {
      missing.push(`${phaseLabel}: sort row ${i + 1} not observed in order: field=${sort.field}; direction=${sort.direction}`);
    }
  }
  return missing;
}

function classifiedGapFromMissing(message) {
  const text = String(message || '');
  const phaseMatch = text.match(/^(before_refresh|after_refresh):\s*/i);
  const phase = phaseMatch ? phaseMatch[1].toLowerCase() : 'unknown';
  let category = 'unknown_gap';
  if (/filter panel extraction failed/i.test(text)) category = 'panel_extraction_gap';
  else if (/sort panel extraction failed/i.test(text)) category = 'panel_extraction_gap';
  else if (/filter row not observed/i.test(text)) category = 'filter_gap';
  else if (/sort row \d+ not observed/i.test(text)) category = 'sort_gap';
  return { category, phase, message: text };
}

export function summarizeGapDetails(gapDetails = []) {
  const summary = {
    total: gapDetails.length,
    filter_gap_count: gapDetails.filter((g) => g.category === 'filter_gap').length,
    sort_gap_count: gapDetails.filter((g) => g.category === 'sort_gap').length,
    panel_extraction_gap_count: gapDetails.filter((g) => g.category === 'panel_extraction_gap').length,
    unknown_gap_count: gapDetails.filter((g) => g.category === 'unknown_gap').length,
    before_refresh_count: gapDetails.filter((g) => g.phase === 'before_refresh').length,
    after_refresh_count: gapDetails.filter((g) => g.phase === 'after_refresh').length
  };
  summary.categories = Array.from(new Set(gapDetails.map((g) => g.category))).sort();
  return summary;
}

export function classifyAirtablePanelReadback(recon) {
  const expectedFilters = recon?.target?.expected_filters || [];
  const expectedSorts = recon?.target?.expected_sorts || [];
  const missing = [];
  missing.push(...compareFiltersForState(recon.before_filter, expectedFilters, 'before_refresh'));
  missing.push(...compareFiltersForState(recon.after_filter, expectedFilters, 'after_refresh'));
  missing.push(...compareSortsForState(recon.before_sort, expectedSorts, 'before_refresh'));
  missing.push(...compareSortsForState(recon.after_sort, expectedSorts, 'after_refresh'));
  const gap_details = missing.map(classifiedGapFromMissing);
  const gap_summary = summarizeGapDetails(gap_details);
  const before_row_state = recon?.row_state_before?.row_state || recon?.row_state_initial?.row_state || null;
  const after_row_state = recon?.row_state_after?.row_state || null;
  const row_state = after_row_state || before_row_state || 'unknown';
  return { ok: missing.length === 0, missing, gap_details, gap_summary, row_state, before_row_state, after_row_state };
}

export function compareAirtablePanelReadback(recon) {
  return classifyAirtablePanelReadback(recon);
}

export const testInternals = Object.freeze({
  includesWholePhrase,
  rowMatchesFilter,
  rowMatchesSort,
  compareAirtablePanelReadback,
  filterReadbackTargetsForResume,
  reloadPageWithRetry,
  targetKeyOfReadbackTarget,
  classifyAirtablePanelReadback,
  summarizeGapDetails,
  uniqueNonEmpty
});
