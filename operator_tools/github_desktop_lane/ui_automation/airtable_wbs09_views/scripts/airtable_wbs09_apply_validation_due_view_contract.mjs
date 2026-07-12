import { norm } from '../../shared/dcoir_ui_common.mjs';

export const TOOL_VERSION = '2026-05-10.wbs09-apply-validation-due-view.4';
export const REQUIRED_TOKEN = 'APPLY_WBS09_VALIDATION_DUE_VIEW';
export const SUPPORTED_TARGET_KEY = 'Operator Tools Registry::WBS09 - Validation Due';

export function parseArgs(argv) {
  const parsed = {
    enableScreenshots: false,
    headless: false,
    useChromeChannel: false,
    userDataDir: null,
    connectCdpUrl: null,
    keepBrowserOpenOnFailure: false,
    targetKeys: [],
    confirmToken: null
  };
  for (let i = 2; i < argv.length; i += 1) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === '--manifest') parsed.manifest = next();
    else if (a === '--output-dir') parsed.outputDir = next();
    else if (a === '--base-url') parsed.baseUrl = next();
    else if (a === '--target-key') parsed.targetKeys.push(next());
    else if (a === '--confirm-token') parsed.confirmToken = next();
    else if (a === '--enable-screenshots') parsed.enableScreenshots = true;
    else if (a === '--headless') parsed.headless = true;
    else if (a === '--use-chrome-channel') parsed.useChromeChannel = true;
    else if (a === '--user-data-dir') parsed.userDataDir = next();
    else if (a === '--connect-cdp-url') parsed.connectCdpUrl = next();
    else if (a === '--keep-browser-open-on-failure') parsed.keepBrowserOpenOnFailure = true;
    else throw new Error(`Unknown argument: ${a}`);
  }
  return parsed;
}

export function normalizeText(value) {
  return String(value || '').replace(/[\u2192\u27f6\u2794]/g, ' -> ').replace(/\s+/g, ' ').trim();
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

export function assertSupportedTarget(target) {
  const key = `${norm(target.table_name)}::${norm(target.view_name)}`;
  if (key !== SUPPORTED_TARGET_KEY) {
    throw new Error(`Unsupported target for this narrow mutation helper: ${key}. Expected ${SUPPORTED_TARGET_KEY}.`);
  }
  if (!Array.isArray(target.expected_filters) || target.expected_filters.length !== 1) {
    throw new Error('Expected exactly one filter in target contract.');
  }
  if (!Array.isArray(target.expected_sorts) || target.expected_sorts.length !== 1) {
    throw new Error('Expected exactly one sort in target contract.');
  }
  const filter = target.expected_filters[0];
  const sort = target.expected_sorts[0];
  const value = Array.isArray(filter.value) ? filter.value.join(',') : String(filter.value || '');
  if (filter.field !== 'review_after' || filter.operator !== 'on or before' || value !== 'today') {
    throw new Error(`Unsupported filter contract: ${JSON.stringify(filter)}. Only review_after on or before today is supported.`);
  }
  if (sort.field !== 'review_after' || String(sort.direction || '').toLowerCase() !== 'asc') {
    throw new Error(`Unsupported sort contract: ${JSON.stringify(sort)}. Only review_after asc is supported.`);
  }
}
