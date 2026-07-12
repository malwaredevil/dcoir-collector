import { nowIso, norm } from './dcoir_ui_common.mjs';

export function normalizeTargetKey(tableName, viewName) {
  return `${norm(tableName)}::${norm(viewName)}`;
}

export function expectedViewStateFromManifestView(view) {
  return {
    table_name: view.table_name,
    table_id: view.table_id,
    view_name: view.view_name,
    view_key: view.view_key || normalizeTargetKey(view.table_name, view.view_name),
    expected_filters: Array.isArray(view.filters) ? view.filters.map((filter, index) => ({
      index: index + 1,
      field: filter.field,
      operator: filter.operator,
      value: filter.value
    })) : [],
    expected_sorts: Array.isArray(view.sorts) ? view.sorts.map((sort, index) => ({
      index: index + 1,
      field: sort.field,
      direction: sort.direction
    })) : []
  };
}

export function selectManifestTargets(manifest, options = {}) {
  const views = Array.isArray(manifest.views) ? manifest.views : [];
  let selected;
  if (options.allViews) {
    selected = views;
  } else if (Array.isArray(options.targetKeys) && options.targetKeys.length > 0) {
    const wanted = new Set(options.targetKeys.map((key) => norm(key).toLowerCase()));
    selected = views.filter((view) => wanted.has(normalizeTargetKey(view.table_name, view.view_name).toLowerCase()) || wanted.has(String(view.view_key || '').toLowerCase()));
  } else if (Array.isArray(options.defaultTargetKeys) && options.defaultTargetKeys.length > 0) {
    const wanted = new Set(options.defaultTargetKeys.map((key) => norm(key).toLowerCase()));
    selected = views.filter((view) => wanted.has(normalizeTargetKey(view.table_name, view.view_name).toLowerCase()) || wanted.has(String(view.view_key || '').toLowerCase()));
  } else {
    selected = [];
  }
  if (selected.length < 1) throw new Error('No Airtable view panel readback targets selected from manifest. Check target keys.');
  return selected.map(expectedViewStateFromManifestView);
}

export function targetKeyOfReadbackTarget(target) {
  return normalizeTargetKey(target?.table_name || '', target?.view_name || '');
}

export function normalizeTargetKeyList(values = []) {
  const out = [];
  for (const value of values || []) {
    const text = norm(value);
    if (!text) continue;
    if (!out.some((existing) => existing.toLowerCase() === text.toLowerCase())) out.push(text);
  }
  return out;
}

function findTargetIndexByKey(targets, key, label) {
  const wanted = norm(key).toLowerCase();
  if (!wanted) return -1;
  const index = (targets || []).findIndex((target) => {
    const canonical = targetKeyOfReadbackTarget(target).toLowerCase();
    const manifestKey = norm(target?.view_key || '').toLowerCase();
    return canonical === wanted || manifestKey === wanted;
  });
  if (index < 0) throw new Error(`${label} was not found in selected target set: ${key}`);
  return index;
}

export function filterReadbackTargetsForResume(targets, options = {}) {
  let selected = Array.isArray(targets) ? targets.slice() : [];
  if (options.afterTargetKey) {
    const index = findTargetIndexByKey(selected, options.afterTargetKey, '--after-target-key');
    selected = selected.slice(index + 1);
  }
  if (options.startAtTargetKey) {
    const index = findTargetIndexByKey(selected, options.startAtTargetKey, '--start-at-target-key');
    selected = selected.slice(index);
  }
  if (Number.isInteger(options.maxTargets) && options.maxTargets > 0) {
    selected = selected.slice(0, options.maxTargets);
  }
  if (selected.length < 1) throw new Error('Resume/target selection produced zero readback targets.');
  return selected;
}

export async function reloadPageWithRetry(page, options = {}) {
  const maxAttempts = Number.isInteger(options.maxAttempts) && options.maxAttempts > 0 ? options.maxAttempts : 3;
  const reloadTimeoutMs = Number.isFinite(options.reloadTimeoutMs) ? options.reloadTimeoutMs : 30000;
  const networkIdleTimeoutMs = Number.isFinite(options.networkIdleTimeoutMs) ? options.networkIdleTimeoutMs : 12000;
  const settleMs = Number.isFinite(options.settleMs) ? options.settleMs : 1200;
  const backoffMs = Number.isFinite(options.backoffMs) ? options.backoffMs : 4000;
  const waitUntil = options.waitUntil || 'domcontentloaded';
  const log = typeof options.log === 'function' ? options.log : null;
  const attempts = [];

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const item = { attempt, max_attempts: maxAttempts, started_at_utc: nowIso(), ok: false, before_url: page.url() };
    try {
      if (log) log('Reload attempt starting.', item);
      await page.reload({ waitUntil, timeout: reloadTimeoutMs });
      await page.waitForLoadState('networkidle', { timeout: networkIdleTimeoutMs }).catch((error) => {
        item.network_idle_warning = String(error?.message || error);
      });
      if (settleMs > 0) await page.waitForTimeout(settleMs);
      item.ok = true;
      item.after_url = page.url();
      item.completed_at_utc = nowIso();
      attempts.push(item);
      if (log) log('Reload attempt completed.', item);
      return { ok: true, attempts, final_url: item.after_url };
    } catch (error) {
      item.error = String(error?.message || error);
      item.after_url = page.url();
      item.completed_at_utc = nowIso();
      attempts.push(item);
      if (log) log('Reload attempt failed.', item);
      if (attempt < maxAttempts && backoffMs > 0) {
        await page.waitForTimeout(backoffMs);
      }
    }
  }
  return { ok: false, attempts, final_url: page.url(), error: attempts[attempts.length - 1]?.error || 'reload failed' };
}
