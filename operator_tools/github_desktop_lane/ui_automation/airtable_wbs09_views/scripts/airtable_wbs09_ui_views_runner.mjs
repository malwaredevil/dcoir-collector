import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline/promises';
import { stdin as input, stdout as output } from 'node:process';

import { parseArgs, selectViews, validateManifest } from './airtable_wbs09_ui_views_contract.mjs';
import { createGridViewAttempt } from './airtable_wbs09_ui_views_create.mjs';
import { calibrateViewConfiguration } from './airtable_wbs09_ui_views_calibration.mjs';
import { ensureDir, log, nowIso, setRuntime, VERSION, writeJson } from './airtable_wbs09_ui_views_runtime.mjs';

export async function runAirtableWbs09UiViewsCli() {
  const args = parseArgs(process.argv);
  const downloads = process.env.DCOIR_DOWNLOADS_DIR;
  if (!downloads || !downloads.trim()) {
    console.error('Missing required Local Configuration Registry variable: DCOIR_DOWNLOADS_DIR');
    process.exit(2);
  }
  const outputDir = args.outputDir || path.join(downloads, `dcoir_wbs09_airtable_ui_views_${new Date().toISOString().replace(/[:.]/g, '')}`);
  ensureDir(outputDir);
  const logPath = path.join(outputDir, 'tool.log');
  setRuntime({ args, outputDir, logPath });

  try {
    log('Starting DCOIR WBS09 Airtable UI view tool.', { version: VERSION });
    if (!args.manifest) throw new Error('Missing --manifest');
    const manifest = JSON.parse(fs.readFileSync(args.manifest, 'utf8'));
    const { views, tables } = validateManifest(manifest);
    const selected = selectViews(views, args);
    const summary = { timestamp_utc: nowIso(), tool_version: VERSION, mode: args.executeCreateViewsOnly ? 'execute_create_views_only' : (args.calibrationMode ? 'calibration' : (args.calibrateViewConfigSelectors ? 'calibrate_view_config_selectors' : 'dry_run')), manifest_view_count: views.length, manifest_table_count: tables.length, selected_view_count: selected.length, start_index: Number(args.startIndex || 1), output_dir: outputDir, downloads_env_var: 'DCOIR_DOWNLOADS_DIR', repo_root_env_var: 'DCOIR_REPO_ROOT', base_id: manifest.base_id, base_url: args.baseUrl || `https://airtable.com/${manifest.base_id}`, dry_run: !args.executeCreateViewsOnly && !args.calibrationMode && !args.calibrateViewConfigSelectors, experimental_configure_filters: Boolean(args.experimentalConfigureFilters), keep_browser_open_on_failure: Boolean(args.keepBrowserOpenOnFailure), views: selected.map(v => ({ table_name: v.table_name, table_id: v.table_id, view_name: v.view_name, view_type: v.view_type, filter_count: (v.filters || []).length, sort_count: (v.sorts || []).length })) };
    writeJson(path.join(outputDir, args.executeCreateViewsOnly ? 'execution_plan.json' : (args.calibrateViewConfigSelectors ? 'view_config_calibration_plan.json' : 'dry_run_report.json')), summary);
    log('Validated manifest and wrote plan.', { selected_view_count: selected.length });
    if (args.capabilityReport) {
      writeJson(path.join(outputDir, 'capability_report.json'), { timestamp_utc: nowIso(), node_version: process.version, playwright_required_for_execute: true, dry_run_requires_browser: false, execution_requires_confirm: 'CREATE_WBS09_NATIVE_VIEWS', start_index_supported: true, view_config_calibration_supported: true, filters_and_sorts: 'calibration only in this draft; no filter/sort mutation attempted', known_risk: 'Airtable UI selectors may drift; calibrate on one view before any configuration execution.' });
    }
    if (!args.executeCreateViewsOnly && !args.calibrationMode && !args.calibrateViewConfigSelectors) { log('Dry run complete. No browser opened and no Airtable mutation attempted.'); process.exit(0); }
    if (args.experimentalConfigureFilters) throw new Error('Filter/sort UI automation is intentionally blocked in this draft. This build supports selector calibration only, not configuration mutation.');
    if (args.executeCreateViewsOnly && args.confirm !== 'CREATE_WBS09_NATIVE_VIEWS') throw new Error('Execute mode requires --confirm CREATE_WBS09_NATIVE_VIEWS');
    if (args.calibrateViewConfigSelectors && selected.length !== 1) throw new Error('View configuration calibration requires exactly one selected manifest view. Pass -TableName and -ViewName.');
    let chromium;
    try { ({ chromium } = await import('playwright')); } catch { throw new Error('Playwright is required. Run the installer script first: Install-DcoirAirtableWbs09UiViewPrereqs.ps1'); }
    const baseUrl = args.baseUrl || `https://airtable.com/${manifest.base_id}`;
    let browser = null;
    let context = null;
    let page = null;
    let closeMode = 'launched';
    if (args.connectCdpUrl) {
      closeMode = 'cdp_disconnect_only';
      log('Connecting to existing Chrome over CDP.', { connect_cdp_url: args.connectCdpUrl });
      browser = await chromium.connectOverCDP(args.connectCdpUrl);
      context = browser.contexts()[0];
      if (!context) throw new Error('CDP connection succeeded but no browser context was available.');
      page = context.pages()[0] || await context.newPage();
    } else if (args.userDataDir) {
      closeMode = 'persistent_context';
      log('Launching persistent browser context.', { user_data_dir: args.userDataDir, chrome_channel: Boolean(args.useChromeChannel) });
      ensureDir(args.userDataDir);
      context = await chromium.launchPersistentContext(args.userDataDir, { headless: Boolean(args.headless), channel: args.useChromeChannel ? 'chrome' : undefined, viewport: { width: 1440, height: 1000 } });
      browser = context.browser();
      page = context.pages()[0] || await context.newPage();
    } else {
      log('Launching browser context.', { chrome_channel: Boolean(args.useChromeChannel) });
      browser = await chromium.launch({ headless: Boolean(args.headless), channel: args.useChromeChannel ? 'chrome' : undefined });
      context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
      page = await context.newPage();
    }
    await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
    const rl = readline.createInterface({ input, output });
    await rl.question('Log into Airtable, confirm the DCOIR base is open, then press Enter. Ctrl+C aborts before any create click. ');
    if (args.calibrationMode) {
      const calibration = { timestamp_utc: nowIso(), url: page.url(), title: await page.title(), note: 'Calibration mode opened Airtable and recorded page metadata only. No view creation attempted.' };
      if (args.enableScreenshots) { const screenshotPath = path.join(outputDir, 'calibration_page.png'); await page.screenshot({ path: screenshotPath, fullPage: true }); calibration.screenshot = screenshotPath; }
      writeJson(path.join(outputDir, 'calibration_report.json'), calibration);
      if (closeMode === 'persistent_context') await context.close(); else await browser.close();
      log('Calibration complete. No Airtable mutation attempted.');
      process.exit(0);
    }
    if (args.calibrateViewConfigSelectors) {
      const report = await calibrateViewConfiguration(page, outputDir, selected[0]);
      if (closeMode === 'persistent_context') await context.close(); else await browser.close();
      log('View configuration selector calibration complete. No Airtable mutation attempted.', { snapshot_count: report.snapshots.length });
      process.exit(0);
    }
    const confirm2 = await rl.question(`About to attempt ${selected.length} native Airtable grid view create action(s), one at a time. Type CREATE_WBS09_NATIVE_VIEWS again to proceed: `);
    if (confirm2 !== 'CREATE_WBS09_NATIVE_VIEWS') throw new Error('Second interactive confirmation did not match; stopped before create-clicks.');
    const results = [];
    let index = 0;
    for (const view of selected) {
      index += 1;
      log('Starting create attempt.', { index, table: view.table_name, view: view.view_name });
      const result = await createGridViewAttempt(page, view, outputDir, index);
      results.push(result);
      writeJson(path.join(outputDir, 'execution_report.partial.json'), { timestamp_utc: nowIso(), results });
      log('Create attempt result.', result);
      if (result.status !== 'create_clicked_unverified' && args.stopOnFirstFailure) break;
    }
    writeJson(path.join(outputDir, 'execution_report.json'), { timestamp_utc: nowIso(), results });
    const failures = results.filter(r => r.status !== 'create_clicked_unverified');
    if (failures.length && args.keepBrowserOpenOnFailure) { writeJson(path.join(outputDir, 'keep_open_failure_report.json'), { timestamp_utc: nowIso(), reason: 'failure_detected', failure_count: failures.length, results }); await rl.question('Failure detected. Browser will remain open for inspection. Press Enter in PowerShell only after you finish inspecting/uploading screenshots. '); }
    if (closeMode === 'persistent_context') await context.close(); else await browser.close();
    log('Execution branch ended.', { result_count: results.length, failure_count: failures.length });
    process.exit(failures.length ? 1 : 0);
  } catch (e) {
    const errorReport = { timestamp_utc: nowIso(), error: String(e && e.message ? e.message : e), stack: e && e.stack ? e.stack : null };
    try { writeJson(path.join(outputDir, 'error_report.json'), errorReport); } catch {}
    console.error(errorReport.error);
    process.exit(1);
  }
}
