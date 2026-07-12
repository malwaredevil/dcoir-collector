import { getFilterOperatorLabel, normalizeFilterValues, filterRequiresValue } from '../../shared/dcoir_airtable_view_config.mjs';
import { captureSnapshot } from './airtable_wbs09_ui_config_one_view_runtime.mjs';
import {
  clearExistingFilterConditions,
  clickPanelText,
  clickToolbarButton,
  selectDropdownValue
} from './airtable_wbs09_ui_config_one_view_clicks.mjs';

function filterValuesForCondition(filter) {
  return normalizeFilterValues(filter);
}

function filterFieldForCondition(filter) {
  return filter ? filter.field : null;
}

async function enterInlineFilterTextValue(page, result, filter, filterIndex) {
  const ordinal = filterIndex + 1;
  const rowY = 268 + (filterIndex * 46);
  const values = filterValuesForCondition(filter);
  if (values.length < 1) throw new Error(`Inline text filter ${ordinal} requires at least one value.`);
  const value = String(values[0]);

  const target = await page.evaluate(({ rowY }) => {
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    const nodes = Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"]'));
    const candidates = nodes.map((el) => {
      const box = el.getBoundingClientRect();
      const placeholder = el.getAttribute('placeholder') || '';
      const aria = el.getAttribute('aria-label') || '';
      const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true';
      return {
        el,
        placeholder,
        aria,
        disabled,
        x: box.x,
        y: box.y,
        w: box.width,
        h: box.height,
        cx: box.x + (box.width / 2),
        cy: box.y + (box.height / 2)
      };
    }).filter((c) => {
      if (!visible(c.el) || c.disabled) return false;
      const nearFilterRow = c.y >= rowY - 60 && c.y <= rowY + 80;
      const likelyValueColumn = c.x >= 650 && c.x <= 1050 && c.w >= 40 && c.h >= 10;
      return nearFilterRow && likelyValueColumn;
    }).sort((a, b) => {
      const aScore = Math.abs((a.y + (a.h / 2)) - rowY) + Math.abs(a.x - 730) / 10;
      const bScore = Math.abs((b.y + (b.h / 2)) - rowY) + Math.abs(b.x - 730) / 10;
      return aScore - bScore;
    });
    const c = candidates[0];
    if (!c) return null;
    return {
      selector: 'inline-filter-text-input',
      placeholder: c.placeholder,
      aria: c.aria,
      x: Math.round(c.x),
      y: Math.round(c.y),
      w: Math.round(c.w),
      h: Math.round(c.h),
      cx: Math.round(c.cx),
      cy: Math.round(c.cy)
    };
  }, { rowY });

  result.steps.push({ action: 'locate_inline_filter_text_input', filter_index: ordinal, value, ...(target || { ok: false }) });
  if (!target) throw new Error(`Could not locate inline text value input for filter ${ordinal}.`);

  await page.mouse.click(target.cx, target.cy);
  await page.waitForTimeout(250);
  const modifier = process.platform === 'darwin' ? 'Meta' : 'Control';
  await page.keyboard.press(`${modifier}+A`).catch(() => {});
  await page.keyboard.press('Backspace').catch(() => {});
  await page.keyboard.type(value, { delay: 15 });
  await page.waitForTimeout(550);
  await page.keyboard.press('Enter').catch(() => {});
  await page.waitForTimeout(900);

  result.steps.push({ action: 'set_inline_filter_text_value', filter_index: ordinal, ok: true, value, selector: target.selector });
  result.snapshots.push(await captureSnapshot(page, `one_view_config_05_filter_${ordinal}_inline_text_value`));
}

async function selectRelativeDateFilterValue(page, result, filter, filterIndex) {
  const ordinal = filterIndex + 1;
  const rowY = 268 + (filterIndex * 46);
  const values = filterValuesForCondition(filter);
  if (values.length < 1) throw new Error(`Relative date filter ${ordinal} requires at least one value.`);
  const value = String(values[0]);

  const relativeDateOpen = await selectDropdownValue(
    page,
    /^(exact date|today|tomorrow|yesterday|one week ago|one month ago|date)$/i,
    { x: 690, y: rowY },
    value,
    `filter-${ordinal}-relative-date-value`
  );

  result.steps.push({ action: 'set_relative_date_filter_value', filter_index: ordinal, value, manifest_operator: filter.operator, ...relativeDateOpen });
  if (!relativeDateOpen.ok) throw new Error(`Could not set relative date value ${value} for filter ${ordinal}.`);

  await page.waitForTimeout(900);
  result.snapshots.push(await captureSnapshot(page, `one_view_config_05_filter_${ordinal}_relative_date_value`));
}

async function configureSingleFilterCondition(page, result, filter, filterIndex) {
  const ordinal = filterIndex + 1;
  const rowY = 268 + (filterIndex * 46);
  const filterField = filterFieldForCondition(filter);

  const add = await clickPanelText(page, /^\+?\s*Add condition$/i, `add-filter-condition-${ordinal}`);
  result.steps.push({ action: 'add_filter_condition', filter_index: ordinal, ...add });
  if (!add.ok) throw new Error(`Could not click Add condition in filter panel for filter ${ordinal}.`);
  await page.waitForTimeout(900);
  result.snapshots.push(await captureSnapshot(page, `one_view_config_02_filter_${ordinal}_condition_added`));

  const field = await selectDropdownValue(page, /^(Work Item|Select a field|Field|Status|Name|delete_stage|approved_to_delete|active|Priority|Queue Rank)$/i, { x: 520, y: rowY }, filterField, `filter-${ordinal}-field`);
  result.steps.push({ action: 'set_filter_field', filter_index: ordinal, field: filterField, ...field });
  if (!field.ok) throw new Error(`Could not select ${filterField} as filter field for filter ${ordinal}.`);
  result.snapshots.push(await captureSnapshot(page, `one_view_config_03_filter_${ordinal}_field`));

  const operatorLabel = getFilterOperatorLabel(filter.operator);
  const operator = await selectDropdownValue(
    page,
    /^(contains|is|is not|is not empty|is empty|is any of|has any of|is one of|is on or before|on or before)$/i,
    { x: 660, y: rowY },
    operatorLabel,
    `filter-${ordinal}-operator`
  );
  result.steps.push({ action: 'set_filter_operator', filter_index: ordinal, operator: operatorLabel, manifest_operator: filter.operator, ...operator });
  if (!operator.ok) throw new Error(`Could not set filter ${ordinal} operator to ${operatorLabel}.`);
  result.snapshots.push(await captureSnapshot(page, `one_view_config_04_filter_${ordinal}_operator`));

  if (!filterRequiresValue(filter)) {
    result.steps.push({ action: 'configure_filter_value_skipped', filter_index: ordinal, ok: true, reason: 'operator does not require a value' });
    await page.waitForTimeout(900);
    result.snapshots.push(await captureSnapshot(page, `one_view_config_05_filter_${ordinal}_no_value_required`));
    return;
  }

  if (filter.operator === 'contains') {
    await enterInlineFilterTextValue(page, result, filter, filterIndex);
    return;
  }

  if (filter.operator === 'on or before') {
    await selectRelativeDateFilterValue(page, result, filter, filterIndex);
    return;
  }

  const valueOpen = await clickPanelText(
    page,
    /^(Select an option|Select options|Choose options|Enter a value|Enter text|Select date|Choose date|Date|Today|today|active|blocked|waiting|todo|in_progress|pending|true|false)$/i,
    `filter-${ordinal}-value-open`
  );
  result.steps.push({ action: 'open_filter_value_selector', filter_index: ordinal, ...valueOpen });
  if (!valueOpen.ok) throw new Error(`Could not open value selector for filter ${ordinal}.`);
  for (const value of filterValuesForCondition(filter)) {
    await page.waitForTimeout(300);
    await page.keyboard.type(String(value), { delay: 15 });
    await page.waitForTimeout(550);
    await page.keyboard.press('Enter');
    result.steps.push({ action: 'select_filter_value', filter_index: ordinal, value, manifest_operator: filter.operator });
  }
  await page.waitForTimeout(900);
  result.snapshots.push(await captureSnapshot(page, `one_view_config_05_filter_${ordinal}_values`));
}

export async function configureFilter(page, result) {
  const target = result.target;
  const filters = Array.isArray(target.filters) ? target.filters : [];
  if (filters.length === 0) {
    result.steps.push({ action: 'configure_filter_skipped', ok: true, reason: 'target has no manifest filters' });
    return;
  }
  const filterClick = await clickToolbarButton(page, /\bFilter\b|Filter rows/, 'filter');
  result.steps.push({ action: 'open_filter_panel', ...filterClick });
  if (!filterClick.ok) throw new Error('Could not open Filter panel.');
  await page.waitForTimeout(700);
  result.snapshots.push(await captureSnapshot(page, 'one_view_config_01_filter_panel_before'));
  await clearExistingFilterConditions(page, result);
  await page.waitForTimeout(700);
  result.snapshots.push(await captureSnapshot(page, 'one_view_config_01b_filter_panel_cleared'));

  for (let filterIndex = 0; filterIndex < filters.length; filterIndex += 1) {
    await configureSingleFilterCondition(page, result, filters[filterIndex], filterIndex);
  }

  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(500);
}
