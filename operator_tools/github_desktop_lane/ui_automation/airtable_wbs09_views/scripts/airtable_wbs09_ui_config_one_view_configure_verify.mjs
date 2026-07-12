import { getFilterOperatorLabel } from '../../shared/dcoir_airtable_view_config.mjs';

export async function verifyPostConditions(page, target) {
  const expectedFilters = Array.isArray(target.filters)
    ? target.filters.map((f, i) => ({ index: i + 1, field: f.field, operator: f.operator, operator_label: getFilterOperatorLabel(f.operator) }))
    : [];
  const expectedSorts = Array.isArray(target.sorts)
    ? target.sorts.map((s, i) => ({ index: i + 1, field: s.field, direction: s.direction }))
    : [];

  const probe = await page.evaluate(({ expectedFilters, expectedSorts }) => {
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }

    const toolbarText = Array.from(document.querySelectorAll('button, [role="button"], div, span'))
      .map((el) => {
        const box = el.getBoundingClientRect();
        return {
          text: (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim(),
          aria: el.getAttribute('aria-label') || '',
          x: box.x,
          y: box.y,
          w: box.width,
          h: box.height,
          visible: visible(el)
        };
      })
      .filter((c) => c.visible && c.y >= 80 && c.y <= 150 && c.x >= 650 && c.x <= 1400)
      .map((c) => `${c.text} ${c.aria}`.trim())
      .join(' ');

    const bodyText = (document.body.innerText || '').replace(/\s+/g, ' ').trim();
    const text = `${toolbarText} ${bodyText}`;
    const lower = text.toLowerCase();

    const hasFilterBadge = expectedFilters.length === 0 || /filtered by/i.test(text);
    const hasFilterFields = expectedFilters.length === 0 || expectedFilters.every((f) => lower.includes(String(f.field || '').toLowerCase()));
    const hasSortBadge = expectedSorts.length === 0 || /sorted by\s+\d+\s+field/i.test(text) || /sorted by/i.test(text);
    const hasSortFields = expectedSorts.length === 0 || expectedSorts.every((s) => lower.includes(String(s.field || '').toLowerCase())) || hasSortBadge;

    const missing = [];
    if (expectedFilters.length > 0 && !(hasFilterBadge || hasFilterFields)) missing.push(`filter post-condition for ${expectedFilters.length} expected filter(s)`);
    if (expectedSorts.length > 0 && !hasSortFields) missing.push(`sort post-condition for ${expectedSorts.length} expected sort(s)`);

    return {
      expected_filter_conditions: expectedFilters,
      expected_sort_conditions: expectedSorts,
      has_filter_badge: hasFilterBadge,
      has_filter_fields: hasFilterFields,
      has_sort_badge: hasSortBadge,
      has_sort_fields: hasSortFields,
      missing,
      toolbar_text_sample: toolbarText.slice(0, 800)
    };
  }, { expectedFilters, expectedSorts });

  return { ok: probe.missing.length === 0, ...probe };
}
export function rollupConfigurationStatus(results) {
  const rows = Array.isArray(results) ? results : [];
  if (rows.length < 1) return 'configuration_not_run';
  return rows.every((r) => r && r.status === 'configuration_verified')
    ? 'configuration_verified'
    : 'configuration_postcondition_failed';
}
