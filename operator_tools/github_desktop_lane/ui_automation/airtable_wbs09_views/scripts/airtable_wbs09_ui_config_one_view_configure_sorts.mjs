import { exactRe, safeName } from '../../shared/dcoir_ui_common.mjs';
import { captureSnapshot } from './airtable_wbs09_ui_config_one_view_runtime.mjs';
import { clickPanelText, clickToolbarButton, selectDropdownValue } from './airtable_wbs09_ui_config_one_view_clicks.mjs';

export async function configureSort(page, result) {
  const target = result.target;
  const sorts = Array.isArray(target.sorts) ? target.sorts : [];
  if (sorts.length === 0) {
    result.steps.push({ action: 'configure_sort_skipped', ok: true, reason: 'target has no manifest sorts' });
    return;
  }
  const sortClick = await clickToolbarButton(page, /\bSort\b|Sort rows/, 'sort');
  result.steps.push({ action: 'open_sort_panel', ...sortClick });
  if (!sortClick.ok) throw new Error('Could not open Sort panel.');
  await page.waitForTimeout(700);
  result.snapshots.push(await captureSnapshot(page, 'one_view_config_06_sort_panel_before'));

  for (let sortIndex = 0; sortIndex < sorts.length; sortIndex += 1) {
    const sort = sorts[sortIndex];
    const sortField = sort.field;
    const sortDirection = sort.direction === 'desc' ? 'descending' : 'ascending';
    const sortOrdinal = sortIndex + 1;

    const addSort = await clickPanelText(page, /^\+?\s*(Add sort|Pick another field to sort by)$/i, `add-sort-${sortOrdinal}`);
    result.steps.push({ action: 'add_sort_or_field_list_ready', sort_index: sortOrdinal, ...addSort });
    if (addSort.ok) await page.waitForTimeout(800);
    else if (sortIndex === 0) result.steps.push({ action: 'sort_panel_field_list_already_visible', ok: true, note: 'No Add sort control found; Airtable displayed the field picker directly or an existing sort row is active.' });
    else throw new Error(`Could not add sort condition ${sortOrdinal}.`);

    let field = await clickPanelText(page, exactRe(sortField), `sort-${sortOrdinal}-field-${safeName(sortField)}-direct`);
    if (!field.ok) field = await selectDropdownValue(page, /^(Pick a field|Select a field|Work Item|Queue Rank|Priority|Name|Execution Lane|Test ID|canonical_parent_plan_id)$/i, { x: 510, y: 268 + ((sortOrdinal - 1) * 42) }, sortField, `sort-${sortOrdinal}-field`);
    result.steps.push({ action: 'set_sort_field', sort_index: sortOrdinal, field: sortField, ...field });
    if (!field.ok) throw new Error(`Could not select ${sortField} as sort field for sort ${sortOrdinal}.`);
    await page.waitForTimeout(700);

    const direction = await selectDropdownValue(page, /^(A\s*â†’\s*Z|1\s*â†’\s*9|Ascending|asc|Z\s*â†’\s*A|9\s*â†’\s*1|Descending|desc)$/i, { x: 725, y: 268 + ((sortOrdinal - 1) * 42) }, sortDirection, `sort-${sortOrdinal}-direction`);
    result.steps.push({ action: 'set_sort_direction', sort_index: sortOrdinal, direction: sortDirection, ...direction });
    if (!direction.ok) {
      if (sortDirection === 'ascending') result.steps.push({ action: 'sort_direction_assumed_default_ascending', ok: true, sort_index: sortOrdinal, note: 'Airtable often defaults to ascending when the sort field is selected and no direction selector is visible.' });
      else throw new Error(`Could not set required descending sort direction for sort ${sortOrdinal}.`);
    }
    await page.waitForTimeout(700);
    result.snapshots.push(await captureSnapshot(page, `one_view_config_07_sort_${sortOrdinal}_configured`));
  }

  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(500);
}
