export function parseArgs(argv) {
  const parsed = {
    dryRun: false,
    executeCreateViewsOnly: false,
    experimentalConfigureFilters: false,
    enableScreenshots: false,
    stopOnFirstFailure: true,
    capabilityReport: false,
    calibrationMode: false,
    calibrateViewConfigSelectors: false,
    headless: false,
    useChromeChannel: false,
    userDataDir: null,
    connectCdpUrl: null,
    keepBrowserOpenOnFailure: false,
    startIndex: 1,
    viewName: null
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === '--manifest') parsed.manifest = next();
    else if (a === '--output-dir') parsed.outputDir = next();
    else if (a === '--base-url') parsed.baseUrl = next();
    else if (a === '--dry-run') parsed.dryRun = true;
    else if (a === '--execute-create-views-only') parsed.executeCreateViewsOnly = true;
    else if (a === '--calibrate-view-config-selectors') parsed.calibrateViewConfigSelectors = true;
    else if (a === '--experimental-configure-filters') parsed.experimentalConfigureFilters = true;
    else if (a === '--confirm') parsed.confirm = next();
    else if (a === '--max-views') parsed.maxViews = Number(next());
    else if (a === '--start-index') parsed.startIndex = Number(next());
    else if (a === '--table-name') parsed.tableName = next();
    else if (a === '--view-name') parsed.viewName = next();
    else if (a === '--enable-screenshots') parsed.enableScreenshots = true;
    else if (a === '--continue-on-failure') parsed.stopOnFirstFailure = false;
    else if (a === '--capability-report') parsed.capabilityReport = true;
    else if (a === '--calibration-mode') parsed.calibrationMode = true;
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
  const keys = new Set();
  for (const view of views) {
    for (const required of ['table_name', 'table_id', 'view_name', 'view_type']) {
      if (!view[required]) throw new Error(`Manifest view missing ${required}: ${JSON.stringify(view)}`);
    }
    const key = `${view.table_name}::${view.view_name}`;
    if (keys.has(key)) throw new Error(`Duplicate manifest view key: ${key}`);
    keys.add(key);
  }
  return { views, tables };
}

export function selectViews(views, args) {
  let selected = views;
  if (args.tableName) selected = selected.filter(v => v.table_name.toLowerCase() === args.tableName.toLowerCase());
  if (args.viewName) selected = selected.filter(v => v.view_name.toLowerCase() === args.viewName.toLowerCase());
  const startIndex = Number(args.startIndex || 1);
  if (!Number.isInteger(startIndex) || startIndex < 1) throw new Error(`--start-index must be an integer >= 1; got ${args.startIndex}`);
  if (startIndex > selected.length + 1) throw new Error(`--start-index ${startIndex} is beyond selected view count ${selected.length}`);
  if (startIndex > 1) selected = selected.slice(startIndex - 1);
  if (args.maxViews && args.maxViews > 0) selected = selected.slice(0, args.maxViews);
  return selected;
}
