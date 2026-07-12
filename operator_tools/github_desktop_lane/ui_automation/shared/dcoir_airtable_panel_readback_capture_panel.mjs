import path from 'node:path';
import { writeJson, safeName, nowIso } from './dcoir_ui_common.mjs';
import { AIRTABLE_UI_GEOMETRY_VERSION } from './dcoir_airtable_ui_geometry.mjs';
import { AIRTABLE_PANEL_READBACK_VERSION } from './dcoir_airtable_panel_readback_contract.mjs';
import { captureDomEvidence } from './dcoir_airtable_panel_readback_capture_dom.mjs';
import { closeOpenAirtablePanel, openAirtablePanel } from './dcoir_airtable_panel_readback_capture_navigation.mjs';

export async function extractOpenAirtablePanel(page, kind) {
  return await page.evaluate((kind) => {
    const normalize = (s) => String(s || '').replace(/[\u2192\u27f6\u2794]/g, ' -> ').replace(/\s+/g, ' ').trim();
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    function topVisible(el, box) {
      const cx = Math.max(0, Math.min(window.innerWidth - 1, box.x + box.width / 2));
      const cy = Math.max(0, Math.min(window.innerHeight - 1, box.y + box.height / 2));
      const top = document.elementFromPoint(cx, cy);
      return !!top && (el === top || el.contains(top) || top.contains(el));
    }

    const markerPhrases = kind === 'sort'
      ? ['sort by', 'add another sort', 'automatically sort records']
      : ['filter', 'in this view, show records', 'add condition', 'copy from another view'];

    const containers = Array.from(document.querySelectorAll('div, section, [role="dialog"], [role="menu"], [data-testid], [class]'))
      .filter(visible)
      .map((el) => {
        const box = el.getBoundingClientRect();
        const text = normalize(el.innerText || el.textContent);
        const lower = text.toLowerCase();
        const markerHits = markerPhrases.filter((phrase) => lower.includes(phrase)).length;
        return { el, text, markerHits, x: box.x, y: box.y, w: box.width, h: box.height, area: box.width * box.height };
      })
      .filter((c) => {
        const lower = c.text.toLowerCase();
        const filterConditionSignal = /where|review_after|is on or before|is before|is after|is empty|is not empty|is checked|is unchecked|today|add condition/.test(lower);
        const sortConditionSignal = /sort by|add another sort|automatically sort records|earliest -> latest|latest -> earliest|ascending|descending|a -> z|z -> a/.test(lower);
        const enoughMarkers = c.markerHits >= 2 || (kind === 'filter' && c.markerHits >= 1 && filterConditionSignal) || (kind === 'sort' && c.markerHits >= 1 && sortConditionSignal);
        if (!enoughMarkers) return false;
        if (c.x < 120 || c.y < 45 || c.w < 170 || c.h < 55) return false;
        if (c.w > 1150 || c.h > 820) return false;
        return true;
      })
      .sort((a, b) => b.markerHits - a.markerHits || a.area - b.area || a.y - b.y || a.x - b.x);

    const panel = containers[0];
    if (!panel) {
      const candidates = Array.from(document.querySelectorAll('button, [role="button"], div, section, [role="dialog"], [role="menu"], [data-testid], [class]'))
        .filter(visible)
        .map((el) => {
          const box = el.getBoundingClientRect();
          const text = normalize(el.innerText || el.textContent);
          const lower = text.toLowerCase();
          const markerHits = markerPhrases.filter((phrase) => lower.includes(phrase)).length;
          return { text: text.slice(0, 300), markerHits, x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width), h: Math.round(box.height) };
        })
        .filter((c) => c.markerHits > 0 || /filtered by|sorted by|review_after|is on or before|today|earliest -> latest/i.test(c.text))
        .sort((a, b) => b.markerHits - a.markerHits || a.y - b.y || a.x - b.x)
        .slice(0, 40);
      return { ok: false, reason: 'panel_container_not_found', panel: null, rows: [], raw_elements: [], container_candidates: candidates };
    }

    const bounds = {
      x: Math.round(panel.x),
      y: Math.round(panel.y),
      w: Math.round(panel.w),
      h: Math.round(panel.h),
      right: Math.round(panel.x + panel.w),
      bottom: Math.round(panel.y + panel.h)
    };

    const raw = Array.from(document.querySelectorAll('button, [role="button"], input, textarea, [contenteditable="true"], [aria-label], [placeholder], div, span'))
      .filter(visible)
      .map((el) => {
        const box = el.getBoundingClientRect();
        const text = normalize(el.innerText || el.textContent);
        const aria = normalize(el.getAttribute('aria-label') || '');
        const placeholder = normalize(el.getAttribute('placeholder') || '');
        const value = normalize(el.value || '');
        const cx = box.x + box.width / 2;
        const cy = box.y + box.height / 2;
        return { el, tag: el.tagName, role: el.getAttribute('role') || '', text, aria, placeholder, value, x: box.x, y: box.y, w: box.width, h: box.height, cx, cy, top: topVisible(el, box) };
      })
      .filter((c) => {
        if (!c.top) return false;
        if (c.x < panel.x - 2 || c.y < panel.y - 2 || c.x + c.w > panel.x + panel.w + 2 || c.y + c.h > panel.y + panel.h + 2) return false;
        if (c.w > panel.w * 0.96 && c.h > 60) return false;
        const content = normalize(`${c.text} ${c.aria} ${c.placeholder} ${c.value}`);
        if (!content) return false;
        if (/Describe what you want to see|Copy from another view|Add condition group|Automatically sort records/i.test(content)) return false;
        if (kind === 'filter' && /^Filter$/i.test(content)) return false;
        if (kind === 'sort' && /^Sort by$/i.test(content)) return false;
        return true;
      })
      .map((c) => ({ tag: c.tag, role: c.role, text: c.text, aria: c.aria, placeholder: c.placeholder, value: c.value, x: Math.round(c.x), y: Math.round(c.y), w: Math.round(c.w), h: Math.round(c.h), cx: Math.round(c.cx), cy: Math.round(c.cy) }))
      .sort((a, b) => a.y - b.y || a.x - b.x);

    const rowCandidates = raw.filter((c) => {
      const content = normalize(`${c.text} ${c.aria} ${c.placeholder} ${c.value}`);
      if (/^Add condition$|^Add another sort$|^Add sort$|^Add condition group$/i.test(content)) return false;
      if (kind === 'filter') return c.y >= panel.y + 65 && c.y <= panel.y + panel.h - 24;
      if (kind === 'sort') return c.y >= panel.y + 42 && c.y <= panel.y + panel.h - 42;
      return true;
    });

    const buckets = [];
    for (const el of rowCandidates) {
      const cy = el.y + Math.round(el.h / 2);
      let bucket = buckets.find((row) => Math.abs(row.center_y - cy) <= 14);
      if (!bucket) {
        bucket = { center_y: cy, elements: [] };
        buckets.push(bucket);
      }
      bucket.elements.push(el);
    }

    function partsFromElements(elements) {
      const parts = [];
      for (const el of elements) {
        for (const part of [el.text, el.aria, el.placeholder, el.value]) {
          const item = normalize(part);
          if (!item) continue;
          if (!parts.some((existing) => existing.toLowerCase() === item.toLowerCase())) parts.push(item);
        }
      }
      return parts;
    }

    const rows = buckets.map((bucket, index) => {
      const elements = bucket.elements.sort((a, b) => a.x - b.x);
      const compact = elements.filter((el) => el.w <= Math.max(260, panel.w * 0.48) || ['INPUT', 'TEXTAREA'].includes(el.tag));
      const fieldZone = compact.filter((el) => el.cx <= panel.x + panel.w * 0.48);
      const operatorZone = compact.filter((el) => el.cx >= panel.x + panel.w * 0.33 && el.cx <= panel.x + panel.w * 0.72);
      const valueZone = compact.filter((el) => el.cx >= panel.x + panel.w * 0.55);
      const directionZone = compact.filter((el) => el.cx >= panel.x + panel.w * 0.45);
      const allParts = partsFromElements(elements);
      return {
        row_index: index + 1,
        y: bucket.center_y,
        text: allParts.join(' | '),
        cells: {
          field_text: partsFromElements(fieldZone).join(' | '),
          operator_text: partsFromElements(operatorZone).join(' | '),
          value_text: partsFromElements(valueZone).join(' | '),
          direction_text: partsFromElements(directionZone).join(' | ')
        },
        elements
      };
    }).filter((row) => row.text && !/^Where$|^and$|^or$/i.test(row.text));

    return { ok: true, panel: bounds, rows, raw_elements: raw };
  }, kind);
}

export async function captureAirtablePanelState(page, outputDir, target, kind, phase, options = {}) {
  const readbackAttempts = [];
  let opened = await openAirtablePanel(page, kind);
  let extracted = await extractOpenAirtablePanel(page, kind);
  readbackAttempts.push({ action: 'open_and_extract_initial', opened, ok: extracted.ok, reason: extracted.reason || null, panel: extracted.panel || null, row_count: Array.isArray(extracted.rows) ? extracted.rows.length : 0 });

  if (!extracted.ok) {
    await page.waitForTimeout(650).catch(() => {});
    const retryExtract = await extractOpenAirtablePanel(page, kind);
    readbackAttempts.push({ action: 'extract_retry_after_wait', ok: retryExtract.ok, reason: retryExtract.reason || null, panel: retryExtract.panel || null, row_count: Array.isArray(retryExtract.rows) ? retryExtract.rows.length : 0 });
    if (retryExtract.ok) extracted = retryExtract;
  }

  if (!extracted.ok) {
    await closeOpenAirtablePanel(page).catch(() => {});
    await page.waitForTimeout(350).catch(() => {});
    const reopened = await openAirtablePanel(page, kind);
    await page.waitForTimeout(1100).catch(() => {});
    const reopenedExtract = await extractOpenAirtablePanel(page, kind);
    readbackAttempts.push({ action: 'reopen_and_extract_retry', opened: reopened, ok: reopenedExtract.ok, reason: reopenedExtract.reason || null, panel: reopenedExtract.panel || null, row_count: Array.isArray(reopenedExtract.rows) ? reopenedExtract.rows.length : 0 });
    opened = reopened;
    if (reopenedExtract.ok) extracted = reopenedExtract;
  }

  const snapshot = await captureDomEvidence(page, outputDir, `${safeName(target.table_name)}_${safeName(target.view_name)}_${phase}_${kind}_panel`, options);
  const state = {
    timestamp_utc: nowIso(),
    tool_version: AIRTABLE_PANEL_READBACK_VERSION,
    geometry_version: AIRTABLE_UI_GEOMETRY_VERSION,
    target,
    phase,
    kind,
    opened,
    readback_attempts: readbackAttempts,
    panel_extraction: { ok: extracted.ok, reason: extracted.reason || null, panel: extracted.panel || null, container_candidates: extracted.container_candidates || [] },
    rows: extracted.rows || [],
    raw_panel_elements: extracted.raw_elements || [],
    snapshot
  };
  const statePath = path.join(outputDir, `${safeName(target.table_name)}_${safeName(target.view_name)}_${phase}_${kind}_state.json`);
  writeJson(statePath, state);
  await closeOpenAirtablePanel(page);
  return { ...state, state_path: statePath };
}
