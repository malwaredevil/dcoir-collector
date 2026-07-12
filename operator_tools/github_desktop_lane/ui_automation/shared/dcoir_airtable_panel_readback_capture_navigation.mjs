import { clickAirtableToolbarButton, clickAirtableViewInSidebar, dismissTransientUi, safeMousePark } from './dcoir_airtable_ui_geometry.mjs';

export async function selectAirtableTableAndView(page, target) {
  const result = { table_id: target.table_id, table_name: target.table_name, view_name: target.view_name, steps: [] };
  await dismissTransientUi(page, 'before-table-navigation');
  const current = new URL(page.url());
  const appId = current.pathname.split('/').filter(Boolean).find((part) => /^app[A-Za-z0-9]+$/.test(part)) || target.base_id;
  if (!appId) throw new Error(`Cannot derive Airtable app id for ${target.table_name}`);
  if (!/^tbl[A-Za-z0-9]+$/.test(String(target.table_id || ''))) throw new Error(`Invalid Airtable table id for ${target.table_name}: ${target.table_id}`);
  const url = `${current.origin}/${appId}/${target.table_id}?blocks=hide`;
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(1200);
  result.steps.push({ action: 'goto_table_by_id', ok: true, url });

  const viewClick = await clickAirtableViewInSidebar(page, target.view_name, { xMin: 40, xMax: 420, yMin: 240, iconAvoidWidth: 82 });
  result.steps.push({ action: 'select_view_by_left_sidebar_only_no_top_view_title', ...viewClick });
  if (!viewClick.ok) throw new Error(`Could not select view ${target.table_name} / ${target.view_name}`);
  await page.waitForTimeout(1200);
  await safeMousePark(page, 'after-select-view');
  return result;
}

export async function openAirtablePanel(page, kind) {
  const panelKind = String(kind || '').toLowerCase();
  if (!['filter', 'sort'].includes(panelKind)) throw new Error(`Unsupported Airtable panel kind: ${kind}`);
  const click = await clickAirtableToolbarButton(page, panelKind, { xMin: 560, xMax: 1450, yMin: 75, yMax: 165 });
  await page.waitForTimeout(900);
  return click;
}

export async function closeOpenAirtablePanel(page) {
  await dismissTransientUi(page, 'close-open-airtable-panel');
}
