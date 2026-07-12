import path from 'node:path';
import readline from 'node:readline/promises';
import { stdin as defaultInput, stdout as defaultOutput } from 'node:process';
import { ensureDir, writeJson, nowIso } from '../../shared/dcoir_ui_common.mjs';
import { VERSION, parseArgs } from './airtable_wbs09_ui_config_one_view_contract.mjs';
import { captureSnapshot, log, setRuntime } from './airtable_wbs09_ui_config_one_view_runtime.mjs';
import { rollupConfigurationStatus } from './airtable_wbs09_ui_config_one_view_configure.mjs';
import { prepareConfigRunPlan } from './airtable_wbs09_ui_config_one_view_runner_plan.mjs';
import { openAirtablePage, closeAirtablePage } from './airtable_wbs09_ui_config_one_view_runner_browser.mjs';
import { configureSelectedTarget } from './airtable_wbs09_ui_config_one_view_runner_target.mjs';

export async function runConfigOneViewCli(argv = process.argv, env = process.env, streams = { input: defaultInput, output: defaultOutput }) {
  const args = parseArgs(argv);
  const downloads = env.DCOIR_DOWNLOADS_DIR;
  if (!downloads || !downloads.trim()) {
    console.error('Missing required Local Configuration Registry variable: DCOIR_DOWNLOADS_DIR');
    return 2;
  }

  const outputDir = args.outputDir || path.join(downloads, `dcoir_wbs09_airtable_ui_views_${new Date().toISOString().replace(/[:.]/g, '')}`);
  ensureDir(outputDir);
  const logPath = path.join(outputDir, 'tool.log');
  setRuntime({ args, outputDir, logPath });

  let browser = null;
  let context = null;
  let page = null;
  let closeMode = 'launched';
  let rl = null;

  try {
    log('Starting DCOIR WBS09 config smoke tool.', { version: VERSION });
    const { manifest, selected, targets, mode, expectedConfirm, schemaGate } = prepareConfigRunPlan(args, outputDir);

    let chromium;
    try {
      ({ chromium } = await import('playwright'));
    } catch {
      throw new Error('Playwright is required. Run the installer script first: Install-DcoirAirtableWbs09UiViewPrereqs.ps1');
    }

    const baseUrl = args.baseUrl || `https://airtable.com/${manifest.base_id}`;
    ({ browser, context, page, closeMode } = await openAirtablePage(chromium, args, baseUrl));
    rl = readline.createInterface({ input: streams.input, output: streams.output });
    await rl.question('Log into Airtable, confirm the DCOIR base is open, then press Enter. Ctrl+C aborts before any configuration click. ');

    const targetList = targets.map((t, i) => `${i + 1}. ${t.table_name} / ${t.view_name}`).join('\n');
    const prompt = args.executeConfigureViewBatch
      ? `About to configure ${targets.length} existing WBS09 Airtable view(s):\n${targetList}\nType ${expectedConfirm} again to proceed: `
      : `About to configure ONE existing WBS09 Airtable view: ${targets[0].table_name} / ${targets[0].view_name}. Type ${expectedConfirm} again to proceed: `;
    const confirm2 = await rl.question(prompt);
    if (confirm2 !== expectedConfirm) throw new Error('Second interactive confirmation did not match; stopped before configuration clicks.');

    if (args.executeConfigureViewBatch) {
      const batchReport = { timestamp_utc: nowIso(), tool_version: VERSION, mode, schema_audit_gate: schemaGate, status: 'started', results: [] };
      for (let i = 0; i < selected.length; i += 1) {
        log('Starting bounded batch target.', { index: i + 1, table: selected[i].table_name, view: selected[i].view_name });
        const result = await configureSelectedTarget(page, selected[i], targets[i], mode, i);
        batchReport.results.push(result);
        batchReport.last_completed_index = i + 1;
        writeJson(path.join(outputDir, 'view_batch_config_report.partial.json'), batchReport);
      }
      batchReport.status = rollupConfigurationStatus(batchReport.results);
      batchReport.completed_at_utc = nowIso();
      writeJson(path.join(outputDir, 'view_batch_config_report.json'), batchReport);
      log('Bounded view-batch configuration branch ended.', { status: batchReport.status, result_count: batchReport.results.length });
    } else {
      const report = await configureSelectedTarget(page, selected[0], targets[0], mode, 0);
      writeJson(path.join(outputDir, 'one_view_config_report.json'), report);
      log('One-view configuration branch ended.', { status: report.status, snapshot_count: report.snapshots.length });
    }

    await closeAirtablePage(context, browser, closeMode);
    return 0;
  } catch (error) {
    const errorReport = {
      timestamp_utc: nowIso(),
      error: String(error && error.message ? error.message : error),
      stack: error && error.stack ? error.stack : null
    };
    try {
      if (page) errorReport.failure_snapshot = await captureSnapshot(page, 'one_view_config_failure');
    } catch (snapshotError) {
      errorReport.failure_snapshot_error = String(snapshotError && snapshotError.message ? snapshotError.message : snapshotError);
    }
    try { writeJson(path.join(outputDir, 'error_report.json'), errorReport); } catch {}
    console.error(errorReport.error);
    try {
      if (page && args.keepBrowserOpenOnFailure && rl) {
        await rl.question('Failure detected. Browser will remain open for inspection. Press Enter in PowerShell only after you finish inspecting/uploading screenshots. ');
      }
    } catch {}
    try { await closeAirtablePage(context, browser, closeMode); } catch {}
    return 1;
  }
}
