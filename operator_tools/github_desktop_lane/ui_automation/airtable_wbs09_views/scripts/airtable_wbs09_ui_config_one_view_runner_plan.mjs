import path from 'node:path';
import { readJsonFile, writeJson, nowIso } from '../../shared/dcoir_ui_common.mjs';
import {
  VERSION,
  validateManifest,
  selectViews,
  oneViewContract,
  verifySchemaAuditGate
} from './airtable_wbs09_ui_config_one_view_contract.mjs';

export function prepareConfigRunPlan(args, outputDir) {
  if (!args.manifest) throw new Error('Missing --manifest');
  const modeCount = [args.executeConfigureOneView, args.executeConfigureViewBatch].filter(Boolean).length;
  if (modeCount !== 1) throw new Error('Specify exactly one mode: --execute-configure-one-view or --execute-configure-view-batch.');
  const mode = args.executeConfigureViewBatch ? 'execute_configure_view_batch' : 'execute_configure_one_view';
  const expectedConfirm = args.executeConfigureViewBatch ? 'CONFIGURE_WBS09_VIEW_BATCH' : 'CONFIGURE_WBS09_ONE_VIEW';
  if (args.confirm !== expectedConfirm) throw new Error(`Configure mode requires --confirm ${expectedConfirm}`);

  const manifest = readJsonFile(args.manifest);
  const { views, tables } = validateManifest(manifest);
  const selected = selectViews(args, views);
  if (args.executeConfigureOneView && selected.length !== 1) throw new Error('One-view configuration requires exactly one selected manifest view. Pass -TableName and -ViewName.');
  if (args.executeConfigureViewBatch) {
    if (selected.length < 1) throw new Error('Batch configuration requires at least one selected view.');
    if (selected.length > 5) throw new Error(`Batch configuration is bounded to at most 5 selected views; got ${selected.length}. Use -MaxViews 5 or lower.`);
    if (!args.maxViews || Number(args.maxViews) < 1) throw new Error('Batch configuration requires -MaxViews 1..5 as an explicit safety bound.');
  }

  const schemaGate = args.executeConfigureViewBatch ? verifySchemaAuditGate(args.schemaAuditJson) : null;
  const targets = selected.map((view) => {
    const contract = oneViewContract(view);
    return { table_name: view.table_name, table_id: view.table_id, view_name: view.view_name, filters: contract.filters, sorts: contract.sorts };
  });

  const plan = {
    timestamp_utc: nowIso(),
    tool_version: VERSION,
    mode,
    manifest_view_count: views.length,
    manifest_table_count: tables.length,
    selected_view_count: selected.length,
    output_dir: outputDir,
    downloads_env_var: 'DCOIR_DOWNLOADS_DIR',
    repo_root_env_var: 'DCOIR_REPO_ROOT',
    base_id: manifest.base_id,
    base_url: args.baseUrl || `https://airtable.com/${manifest.base_id}`,
    supported_target_contract: args.executeConfigureViewBatch ? 'bounded_batch_max_five_views_each_max_two_filters_max_five_sorts_schema_audit_pass_required' : 'generic_single_view_max_two_filters_max_five_sorts',
    schema_audit_gate: schemaGate,
    targets
  };

  const planName = args.executeConfigureViewBatch ? 'view_batch_config_plan.json' : 'one_view_config_plan.json';
  writeJson(path.join(outputDir, planName), plan);
  return { manifest, selected, targets, mode, expectedConfirm, schemaGate };
}
