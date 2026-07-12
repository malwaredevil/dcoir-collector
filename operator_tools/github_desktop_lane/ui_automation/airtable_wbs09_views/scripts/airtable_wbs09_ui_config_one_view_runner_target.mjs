import { nowIso, safeName } from '../../shared/dcoir_ui_common.mjs';
import { VERSION } from './airtable_wbs09_ui_config_one_view_contract.mjs';
import { captureSnapshot, state } from './airtable_wbs09_ui_config_one_view_runtime.mjs';
import { configureFilter, configureSort, verifyPostConditions } from './airtable_wbs09_ui_config_one_view_configure.mjs';
import { verifyViewLoaded } from './airtable_wbs09_ui_config_one_view_runner_navigation.mjs';

export async function configureSelectedTarget(page, view, target, mode, index) {
  const prefix = mode === 'execute_configure_view_batch'
    ? `batch_${String(index + 1).padStart(3, '0')}_${safeName(view.table_name)}_${safeName(view.view_name)}`
    : '';
  state.args.activeSnapshotPrefix = prefix;
  const report = { timestamp_utc: nowIso(), tool_version: VERSION, mode, target, steps: [], snapshots: [], status: 'started' };
  const loaded = await verifyViewLoaded(page, view);
  report.steps.push({ action: 'select_table', ...loaded.tableClick });
  report.steps.push({ action: 'select_view', ...loaded.viewClick });
  if (!loaded.tableClick.ok || !loaded.viewClick.ok) throw new Error(`Could not safely select target table/view before configuration: ${view.table_name} / ${view.view_name}.`);
  report.snapshots.push(await captureSnapshot(page, 'one_view_config_00_target_loaded'));
  await configureFilter(page, report);
  await configureSort(page, report);
  report.completed_at_utc = nowIso();
  report.snapshots.push(await captureSnapshot(page, 'one_view_config_08_final_unverified'));
  const postConditions = await verifyPostConditions(page, target);
  report.steps.push({ action: 'verify_post_conditions', ...postConditions });
  if (!postConditions.ok) {
    report.status = 'configuration_postcondition_failed';
    throw new Error(`Post-condition verification failed for ${target.table_name} / ${target.view_name}: ${postConditions.missing.join(', ')}`);
  }
  report.status = 'configuration_verified';
  state.args.activeSnapshotPrefix = '';
  return report;
}
