import { fieldToken, lowerText } from './dcoir_airtable_panel_actions_contract.mjs';

export function clickableElementFromRow(row, matcher, fallbackPoint = null) {
  const elements = Array.isArray(row?.elements) ? row.elements : [];
  const matches = elements
    .filter((element) => {
      const text = lowerText(`${element.text || ''} ${element.aria || ''} ${element.placeholder || ''} ${element.value || ''}`);
      return matcher(element, text);
    })
    .sort((a, b) => {
      const aButton = String(a.role || '').toLowerCase() === 'button' ? 0 : 1;
      const bButton = String(b.role || '').toLowerCase() === 'button' ? 0 : 1;
      const areaA = Number(a.w || 0) * Number(a.h || 0);
      const areaB = Number(b.w || 0) * Number(b.h || 0);
      return aButton - bButton || areaA - areaB || Number(a.x || 0) - Number(b.x || 0);
    });
  const element = matches[0];
  if (element) {
    return {
      x: Number(element.cx ?? (Number(element.x || 0) + Number(element.w || 0) / 2)),
      y: Number(element.cy ?? (Number(element.y || 0) + Number(element.h || 0) / 2)),
      source: { text: element.text || '', aria: element.aria || '', role: element.role || '', x: element.x, y: element.y, w: element.w, h: element.h }
    };
  }
  return fallbackPoint ? { ...fallbackPoint, source: { fallback: true } } : null;
}

export function chooseFieldPoint(row, fieldName, panel) {
  const wanted = fieldToken(fieldName);
  return clickableElementFromRow(row, (element, text) => {
    if (String(element.role || '').toLowerCase() !== 'button') return false;
    return text === wanted || text.includes(wanted);
  }, { x: Number(panel?.x || 285) + 150, y: Number(row?.y || Number(panel?.y || 129) + 138) });
}

export function chooseOperatorPoint(row, panel) {
  return clickableElementFromRow(row, (element, text) => {
    if (String(element.role || '').toLowerCase() !== 'button') return false;
    if (/remove item|reorder item/.test(text)) return false;
    return /^(is|is not|is on or before|is on or after|is before|is after|contains|does not contain)/.test(text);
  }, { x: Number(panel?.x || 285) + 276, y: Number(row?.y || Number(panel?.y || 129) + 138) });
}

export function chooseValuePoint(row, panel) {
  return clickableElementFromRow(row, (element, text) => {
    if (String(element.role || '').toLowerCase() !== 'button') return false;
    if (/remove item|reorder item/.test(text)) return false;
    return /today|tomorrow|yesterday|exact date|enter a date|this week|this month|gmt|cest/.test(text);
  }, { x: Number(panel?.x || 285) + 450, y: Number(row?.y || Number(panel?.y || 129) + 138) });
}

export async function clickPoint(page, point, label, steps) {
  if (!point || !Number.isFinite(Number(point.x)) || !Number.isFinite(Number(point.y))) {
    throw new Error(`Cannot click ${label}: missing finite coordinates.`);
  }
  await page.mouse.click(Math.round(Number(point.x)), Math.round(Number(point.y)));
  const step = { action: label, x: Math.round(Number(point.x)), y: Math.round(Number(point.y)), source: point.source || null };
  if (steps) steps.push(step);
  return step;
}
