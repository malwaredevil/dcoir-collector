import fs from 'node:fs';
import { readJsonFile } from '../../shared/dcoir_ui_common.mjs';
import { validateViewConfigContract } from '../../shared/dcoir_airtable_view_config.mjs';

export const VERSION = '2026-05-10.draft30-relative-date-filter-values';

export function parseArgs(argv) {
  const parsed = {
    executeConfigureOneView: false,
    executeConfigureViewBatch: false,
    enableScreenshots: false,
    stopOnFirstFailure: true,
    headless: false,
    useChromeChannel: false,
    userDataDir: null,
    connectCdpUrl: null,
    keepBrowserOpenOnFailure: false,
    startIndex: 1,
    viewName: null
  };
  for (let i = 2; i < argv.length; i += 1) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === '--manifest') parsed.manifest = next();
    else if (a === '--output-dir') parsed.outputDir = next();
    else if (a === '--base-url') parsed.baseUrl = next();
    else if (a === '--execute-configure-one-view') parsed.executeConfigureOneView = true;
    else if (a === '--execute-configure-view-batch') parsed.executeConfigureViewBatch = true;
    else if (a === '--confirm') parsed.confirm = next();
    else if (a === '--max-views') parsed.maxViews = Number(next());
    else if (a === '--start-index') parsed.startIndex = Number(next());
    else if (a === '--table-name') parsed.tableName = next();
    else if (a === '--view-name') parsed.viewName = next();
    else if (a === '--schema-audit-json') parsed.schemaAuditJson = next();
    else if (a === '--enable-screenshots') parsed.enableScreenshots = true;
    else if (a === '--continue-on-failure') parsed.stopOnFirstFailure = false;
    else if (a === '--headless') parsed.headless = true;
    else if (a === '--use-chrome-channel') parsed.useChromeChannel = true;
    else if (a === '--user-data-dir') parsed.userDataDir = next();
    else if (a === '--connect-cdp-url') parsed.connectCdpUrl = next();
    else if (a === '--keep-browser-open-on-failure') parsed.keepBrowserOpenOnFailure = true;
    else throw new Error(`Unknown argument: ${a}`);
  }
  return parsed;
}

export function validateManifest(manifest) {
  const views = manifest.views || [];
  const tables = manifest.tables || [];
  if (manifest.view_count !== 65 || views.length !== 65) throw new Error(`Manifest must contain exactly 65 views; got ${views.length}`);
  if (manifest.table_count !== 21 || tables.length !== 21) throw new Error(`Manifest must contain exactly 21 tables; got ${tables.length}`);
  return { views, tables };
}

export function selectViews(args, views) {
  let selected = views;
  if (args.tableName) selected = selected.filter(v => String(v.table_name).toLowerCase() === args.tableName.toLowerCase());
  if (args.viewName) selected = selected.filter(v => String(v.view_name).toLowerCase() === args.viewName.toLowerCase());
  const startIndex = Number(args.startIndex || 1);
  if (!Number.isInteger(startIndex) || startIndex < 1) throw new Error(`--start-index must be an integer >= 1; got ${args.startIndex}`);
  if (startIndex > selected.length + 1) throw new Error(`--start-index ${startIndex} is beyond selected view count ${selected.length}`);
  if (startIndex > 1) selected = selected.slice(startIndex - 1);
  if (args.maxViews && args.maxViews > 0) selected = selected.slice(0, args.maxViews);
  return selected;
}

export function oneViewContract(view) {
  return validateViewConfigContract(view, { maxFilters: 2, maxSorts: 5 });
}
export function verifySchemaAuditGate(schemaAuditJson) {
  if (!schemaAuditJson || !String(schemaAuditJson).trim()) throw new Error('Batch configuration requires --schema-audit-json pointing to a fresh PASS audit report.');
  if (!fs.existsSync(schemaAuditJson)) throw new Error(`Schema audit JSON not found: ${schemaAuditJson}`);
  const audit = readJsonFile(schemaAuditJson);
  const status = audit.status;
  const errors = Number(audit.error_count || 0);
  const warnings = Number(audit.warning_count || 0);
  const views = Number(audit.manifest_view_count || 0);
  if (status !== 'PASS' || errors !== 0 || warnings !== 0 || views !== 65) {
    throw new Error(`Schema audit gate failed. Expected PASS/errors=0/warnings=0/views=65; got status=${status}, errors=${errors}, warnings=${warnings}, views=${views}.`);
  }
  return { status, error_count: errors, warning_count: warnings, manifest_view_count: views, source: schemaAuditJson };
}
