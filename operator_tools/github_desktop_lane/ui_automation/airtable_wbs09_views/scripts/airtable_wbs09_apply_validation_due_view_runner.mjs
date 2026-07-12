import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline/promises';
import { stdin as input, stdout as output } from 'node:process';
import { ensureDir, readJsonFile, writeJson, nowIso, safeName } from '../../shared/dcoir_ui_common.mjs';
import { selectManifestTargets, captureDomEvidence } from '../../shared/dcoir_airtable_panel_readback.mjs';
import {
  REQUIRED_TOKEN,
  SUPPORTED_TARGET_KEY,
  TOOL_VERSION,
  assertSupportedTarget,
  parseArgs
} from './airtable_wbs09_apply_validation_due_view_contract.mjs';
import { closeBrowser, openBrowser } from './airtable_wbs09_apply_validation_due_view_browser.mjs';
import {
  AIRTABLE_PANEL_ACTIONS_VERSION,
  AIRTABLE_PANEL_DISCOVERY_VERSION,
  AIRTABLE_PANEL_READBACK_VERSION,
  applyOneTarget
} from './airtable_wbs09_apply_validation_due_view_mutations.mjs';

export async function runApplyValidationDueViewCli(argv = process.argv, env = process.env) {
  const args = parseArgs(argv);
  const downloads = env.DCOIR_DOWNLOADS_DIR;
  if (!downloads || !downloads.trim()) {
    console.error('Missing required Local Configuration Registry variable: DCOIR_DOWNLOADS_DIR');
    return 2;
  }
  if (args.confirmToken !== REQUIRED_TOKEN) {
    console.error(`Missing required --confirm-token ${REQUIRED_TOKEN}`);
    return 2;
  }

  const outputDir = args.outputDir || path.join(downloads, `dcoir_wbs09_apply_validation_due_view_${new Date().toISOString().replace(/[:.]/g, '')}`);
  ensureDir(outputDir);
  const logPath = path.join(outputDir, 'apply_validation_due_view.log');
  function log(message, obj) {
    const line = `${nowIso()} ${message}${obj ? ' ' + JSON.stringify(obj) : ''}`;
    fs.appendFileSync(logPath, line + '\n', 'utf8');
    console.log(line);
  }

  let browserState = null;
  let rl = null;
  try {
    log('Starting DCOIR WBS09 apply validation-due view tool.', {
      version: TOOL_VERSION,
      shared_panel_readback_version: AIRTABLE_PANEL_READBACK_VERSION,
      shared_panel_discovery_version: AIRTABLE_PANEL_DISCOVERY_VERSION,
      shared_panel_actions_version: AIRTABLE_PANEL_ACTIONS_VERSION
    });
    if (!args.manifest) throw new Error('Missing --manifest');
    const manifest = readJsonFile(args.manifest);
    const targets = selectManifestTargets(manifest, { targetKeys: args.targetKeys });
    if (targets.length !== 1) throw new Error('This tool requires exactly one -TargetKey.');
    const target = targets[0];
    target.base_id = manifest.base_id;
    assertSupportedTarget(target);
    const baseUrl = args.baseUrl || `https://airtable.com/${manifest.base_id}`;

    browserState = await openBrowser(args, baseUrl);
    rl = readline.createInterface({ input, output });
    await rl.question('Airtable validation-due apply: log into Airtable, confirm the DCOIR base is open, then press Enter. Ctrl+C aborts before mutation gate. ');
    const typed = await rl.question(`About to add/verify only the ${SUPPORTED_TARGET_KEY} review_after filter/sort. Type ${REQUIRED_TOKEN} again to proceed: `);
    if (typed.trim() !== REQUIRED_TOKEN) throw new Error('Confirmation token mismatch. Aborting before mutation.');

    const runtime = { page: browserState.page, outputDir, args, log };
    const result = await applyOneTarget(runtime, target);
    const reportPath = path.join(outputDir, `${safeName(target.table_name)}_${safeName(target.view_name)}_apply_validation_due_view_report.json`);
    writeJson(reportPath, result);
    const rollup = {
      timestamp_utc: nowIso(),
      tool_version: TOOL_VERSION,
      status: result.status,
      target_count: 1,
      mutation_attempted: Boolean(result.mutation_attempted),
      mutation_types: result.mutation_types || [],
      report_path: reportPath
    };
    writeJson(path.join(outputDir, 'apply_validation_due_view_rollup.json'), rollup);
    log('Apply validation-due view completed.', rollup);
    const ok = ['already_correct_noop', 'validation_due_view_verified_after_refresh'].includes(result.status);
    await closeBrowser(browserState, args, ok, rl);
    return ok ? 0 : 1;
  } catch (error) {
    const failure = {
      timestamp_utc: nowIso(),
      tool_version: TOOL_VERSION,
      status: 'apply_validation_due_view_failed',
      error: String(error && error.message ? error.message : error)
    };
    try {
      if (browserState?.page) {
        failure.snapshot = await captureDomEvidence(browserState.page, outputDir, 'apply_validation_due_view_failure', args);
      }
    } catch {}
    writeJson(path.join(outputDir, 'apply_validation_due_view_failed.json'), failure);
    log('Apply validation-due view failed.', { error: failure.error });
    await closeBrowser(browserState, args, false, rl);
    return 1;
  } finally {
    if (rl) rl.close();
  }
}
