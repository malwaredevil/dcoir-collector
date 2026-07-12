export const AIRTABLE_PANEL_ACTIONS_VERSION = '2026-05-17.panel-actions.8-export-dropdown-scroll';

export function normalizeText(value) {
  return String(value || '')
    .replace(/[\u2192\u27f6\u2794]/g, ' -> ')
    .replace(/[\u2026]/g, '...')
    .replace(/\s+/g, ' ')
    .trim();
}

export function lowerText(value) {
  return normalizeText(value).toLowerCase();
}

export function regexEscape(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function exactTextPattern(value) {
  return new RegExp(`^${regexEscape(normalizeText(value))}$`, 'i');
}

export function fieldToken(fieldName) {
  return lowerText(fieldName).replace(/\s+/g, '_');
}

export function rowText(row) {
  return lowerText(`${row?.text || ''} ${Object.values(row?.cells || {}).join(' ')}`);
}

export function isInstructionFilterRow(row) {
  const text = rowText(row);
  return !text || /in this view, show records|add condition|learn more about filtering/.test(text);
}

export function isExpectedRelativeDateFilterRow(row, spec = {}) {
  const text = rowText(row);
  if (!text) return false;
  const field = fieldToken(spec.field || '');
  const operator = lowerText(spec.operator || '').replace(/^is\s+/, '');
  const value = lowerText(spec.value || '');
  return text.includes(field)
    && text.includes(operator)
    && (!value || text.includes(value));
}

export function summarizeFilterRowsForField(panelState, fieldName) {
  const wanted = fieldToken(fieldName);
  const rows = Array.isArray(panelState?.rows) ? panelState.rows : [];
  return rows
    .filter((row) => !isInstructionFilterRow(row))
    .filter((row) => rowText(row).includes(wanted))
    .map((row) => ({ ...row, normalized_text: rowText(row) }));
}
