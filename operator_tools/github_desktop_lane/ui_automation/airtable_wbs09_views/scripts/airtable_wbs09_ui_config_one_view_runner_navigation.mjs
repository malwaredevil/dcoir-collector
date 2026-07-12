import { clickExistingView, clickFirst } from './airtable_wbs09_ui_config_one_view_clicks.mjs';

export async function gotoTableById(page, view) {
  const previousUrl = page.url();
  try {
    const current = new URL(previousUrl);
    const appId = current.pathname.split('/').filter(Boolean).find((part) => /^app[A-Za-z0-9]+$/.test(part));
    if (!appId) return { ok: false, selector: 'url:table-id-navigation', previous_url: previousUrl, error: 'Could not derive Airtable app id from current URL.' };
    if (!/^tbl[A-Za-z0-9]+$/.test(String(view.table_id || ''))) return { ok: false, selector: 'url:table-id-navigation', previous_url: previousUrl, error: `Invalid or missing table id: ${view.table_id}` };
    const targetUrl = `${current.origin}/${appId}/${view.table_id}?blocks=hide`;
    await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(1600);
    return { ok: true, selector: 'url:table-id-navigation', previous_url: previousUrl, url: targetUrl };
  } catch (error) {
    return { ok: false, selector: 'url:table-id-navigation', previous_url: previousUrl, error: String(error && error.message ? error.message : error) };
  }
}

export async function verifyViewLoaded(page, view) {
  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(300);
  let tableClick = await gotoTableById(page, view);
  if (!tableClick.ok) {
    tableClick = await clickFirst(page, [page.getByText(view.table_name, { exact: true }), `[title="${String(view.table_name).replace(/"/g, '\\"')}"]`, `text="${String(view.table_name).replace(/"/g, '\\"')}"`], { timeout: 3000 });
  }
  await page.waitForTimeout(900);
  const viewClick = await clickExistingView(page, view.view_name);
  await page.waitForTimeout(1200);
  return { tableClick, viewClick };
}
