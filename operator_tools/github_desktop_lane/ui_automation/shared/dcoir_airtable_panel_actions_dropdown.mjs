async function clickVisibleOption(page, pattern, label, bounds = {}) {
  // Return the exact visible option coordinates from the DOM, then click them with
  // Playwright's native mouse. Airtable's custom dropdowns often ignore el.click()
  // synthetic DOM events even when the option node is visible and correctly matched.
  const found = await page.evaluate(({ source, flags, bounds, label }) => {
    const re = new RegExp(source, flags);
    const normalize = (s) => String(s || '').replace(/[\u2192\u27f6\u2794]/g, ' -> ').replace(/[\u2026]/g, '...').replace(/\s+/g, ' ').trim();
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
    const xMin = Number.isFinite(bounds.xMin) ? bounds.xMin : 0;
    const xMax = Number.isFinite(bounds.xMax) ? bounds.xMax : window.innerWidth;
    const yMin = Number.isFinite(bounds.yMin) ? bounds.yMin : 0;
    const yMax = Number.isFinite(bounds.yMax) ? bounds.yMax : window.innerHeight;
    const candidates = Array.from(document.querySelectorAll('[role="option"], [role="menuitem"], li, button, [role="button"], div, span'))
      .filter(visible)
      .map((el) => {
        const box = el.getBoundingClientRect();
        return {
          text: normalize(el.innerText || el.textContent || el.getAttribute('aria-label') || ''),
          aria: normalize(el.getAttribute('aria-label') || ''),
          role: el.getAttribute('role') || '',
          tag: el.tagName || '',
          x: box.x,
          y: box.y,
          w: box.width,
          h: box.height,
          cx: box.x + box.width / 2,
          cy: box.y + box.height / 2,
          area: box.width * box.height,
          top: topVisible(el, box)
        };
      })
      .filter((item) => {
        if (!item.top) return false;
        if (!item.text || item.text.length > 160) return false;
        if (!re.test(item.text) && !re.test(item.aria)) return false;
        if (item.x < xMin || item.x > xMax || item.y < yMin || item.y > yMax) return false;
        if (item.w < 8 || item.h < 8 || item.w > 720 || item.h > 120) return false;
        if (/help \/ quick tips|learn more about|sort records|filter records/.test(item.text.toLowerCase())) return false;
        return true;
      })
      .sort((a, b) => {
        const ar = ['option', 'menuitem'].includes(String(a.role || '').toLowerCase()) || String(a.tag || '').toLowerCase() === 'li' ? 0 : 1;
        const br = ['option', 'menuitem'].includes(String(b.role || '').toLowerCase()) || String(b.tag || '').toLowerCase() === 'li' ? 0 : 1;
        return ar - br || a.area - b.area || a.y - b.y || a.x - b.x;
      });
    const chosen = candidates[0];
    if (!chosen) return { ok: false, label, method: 'native-visible-option' };
    return {
      ok: true,
      label,
      method: 'native-visible-option',
      text: chosen.text,
      aria: chosen.aria,
      role: chosen.role,
      tag: chosen.tag,
      x: Math.round(chosen.x),
      y: Math.round(chosen.y),
      w: Math.round(chosen.w),
      h: Math.round(chosen.h),
      cx: Math.round(chosen.cx),
      cy: Math.round(chosen.cy)
    };
  }, { source: pattern.source, flags: pattern.flags, bounds, label });

  if (!found.ok) return found;
  await page.mouse.click(found.cx, found.cy).catch(async () => {
    await page.mouse.move(found.cx, found.cy).catch(() => {});
    await page.waitForTimeout(100).catch(() => {});
    await page.mouse.down().catch(() => {});
    await page.mouse.up().catch(() => {});
  });
  await page.waitForTimeout(650).catch(() => {});
  return found;
}

async function clickOptionFromCompositePopupText(page, pattern, label, bounds = {}, steps = null) {
  const result = await page.evaluate(({ source, flags, bounds, label }) => {
    const re = new RegExp(source, flags);
    const normalize = (s) => String(s || '')
      .replace(/[\u2192\u27f6\u2794]/g, ' -> ')
      .replace(/[\u2026]/g, '...')
      .replace(/\s+/g, ' ')
      .trim();
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    function topVisibleAt(x, y, el) {
      const top = document.elementFromPoint(Math.max(0, Math.min(window.innerWidth - 1, x)), Math.max(0, Math.min(window.innerHeight - 1, y)));
      return !!top && (el === top || el.contains(top) || top.contains(el));
    }
    const xMin = Number.isFinite(bounds.xMin) ? bounds.xMin : 0;
    const xMax = Number.isFinite(bounds.xMax) ? bounds.xMax : window.innerWidth;
    const yMin = Number.isFinite(bounds.yMin) ? bounds.yMin : 0;
    const yMax = Number.isFinite(bounds.yMax) ? bounds.yMax : window.innerHeight;
    const menuNeedles = ['today', 'tomorrow', 'yesterday', 'one week ago', 'exact date'];
    const candidates = Array.from(document.querySelectorAll('div, [role="listbox"], [role="menu"], [class], [data-testid]'))
      .filter(visible)
      .map((el) => {
        const box = el.getBoundingClientRect();
        const raw = String(el.innerText || el.textContent || '');
        const text = normalize(raw);
        const lines = raw.split(/\n+/).map((line) => normalize(line)).filter(Boolean);
        return { el, box, text, lines, role: el.getAttribute('role') || '' };
      })
      .filter((item) => {
        const box = item.box;
        if (box.x < xMin - 60 || box.x > xMax + 60 || box.y < yMin - 80 || box.y > yMax + 80) return false;
        if (box.width < 80 || box.width > 520 || box.height < 60 || box.height > 460) return false;
        const lower = item.text.toLowerCase();
        if (/help \/ quick tips|sort records|filter records|learn more about/i.test(lower)) return false;
        const needleHits = menuNeedles.filter((needle) => lower.includes(needle)).length;
        if (needleHits < 3) return false;
        if (!item.lines.some((line) => re.test(line))) return false;
        return true;
      })
      .sort((a, b) => {
        const ar = ['listbox', 'menu'].includes(String(a.role || '').toLowerCase()) ? 0 : 1;
        const br = ['listbox', 'menu'].includes(String(b.role || '').toLowerCase()) ? 0 : 1;
        const areaA = a.box.width * a.box.height;
        const areaB = b.box.width * b.box.height;
        return ar - br || areaA - areaB || a.box.y - b.box.y || a.box.x - b.box.x;
      });
    const menu = candidates[0];
    if (!menu) return { ok: false, label, method: 'composite-popup-text', reason: 'no-composite-popup' };
    const targetIndex = menu.lines.findIndex((line) => re.test(line));
    if (targetIndex < 0) return { ok: false, label, method: 'composite-popup-text', reason: 'target-line-not-found', lines: menu.lines.slice(0, 14) };
    const box = menu.box;
    const rowHeight = Math.max(22, Math.min(40, box.height / Math.max(menu.lines.length, 1)));
    const clickX = Math.round(box.x + Math.min(Math.max(32, box.width * 0.28), box.width - 24));
    const clickY = Math.round(box.y + rowHeight * targetIndex + rowHeight / 2);
    if (!topVisibleAt(clickX, clickY, menu.el)) {
      return { ok: false, label, method: 'composite-popup-text', reason: 'click-point-not-top-visible', x: clickX, y: clickY, targetLine: menu.lines[targetIndex], lines: menu.lines.slice(0, 14) };
    }
    return {
      ok: true,
      label,
      method: 'composite-popup-text',
      targetLine: menu.lines[targetIndex],
      targetIndex,
      x: clickX,
      y: clickY,
      box: { x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width), h: Math.round(box.height) },
      lines: menu.lines.slice(0, 14)
    };
  }, { source: pattern.source, flags: pattern.flags, bounds, label });
  if (result.ok && Number.isFinite(Number(result.x)) && Number.isFinite(Number(result.y))) {
    await page.mouse.click(Number(result.x), Number(result.y)).catch(async () => {
      await page.mouse.move(Number(result.x), Number(result.y)).catch(() => {});
      await page.waitForTimeout(100).catch(() => {});
      await page.mouse.down().catch(() => {});
      await page.mouse.up().catch(() => {});
    });
  }
  await page.waitForTimeout(700).catch(() => {});
  if (steps) steps.push({ action: label, ...result });
  return result;
}

async function scrollCandidateDropdown(page, bounds = {}, mode = 'top', offset = 0) {
  return page.evaluate(({ bounds, mode, offset }) => {
    const xMin = Number.isFinite(bounds.xMin) ? bounds.xMin : 0;
    const xMax = Number.isFinite(bounds.xMax) ? bounds.xMax : window.innerWidth;
    const yMin = Number.isFinite(bounds.yMin) ? bounds.yMin : 0;
    const yMax = Number.isFinite(bounds.yMax) ? bounds.yMax : window.innerHeight;
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    function intersects(box) {
      return box.x + box.width >= xMin - 40
        && box.x <= xMax + 40
        && box.y + box.height >= yMin - 40
        && box.y <= yMax + 40;
    }
    const candidates = Array.from(document.querySelectorAll('div, [role="listbox"], [role="menu"], [data-testid], [class]'))
      .filter(visible)
      .map((el) => {
        const box = el.getBoundingClientRect();
        return {
          el,
          x: box.x,
          y: box.y,
          w: box.width,
          h: box.height,
          area: box.width * box.height,
          scrollHeight: el.scrollHeight,
          clientHeight: el.clientHeight,
          scrollTop: el.scrollTop,
          role: el.getAttribute('role') || '',
          text: String(el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 240)
        };
      })
      .filter((item) => {
        if (!intersects(item)) return false;
        if (item.w < 80 || item.w > 760 || item.h < 40 || item.h > 720) return false;
        if (item.scrollHeight <= item.clientHeight + 8) return false;
        if (/help \/ quick tips|sort records|filter records/i.test(item.text)) return false;
        return true;
      })
      .sort((a, b) => {
        const aRole = ['listbox', 'menu'].includes(String(a.role || '').toLowerCase()) ? 0 : 1;
        const bRole = ['listbox', 'menu'].includes(String(b.role || '').toLowerCase()) ? 0 : 1;
        return aRole - bRole || a.area - b.area || b.scrollHeight - a.scrollHeight || a.y - b.y;
      });
    const chosen = candidates[0];
    if (!chosen) return { ok: false, mode, reason: 'no-scrollable-dropdown-found' };
    const maxScroll = Math.max(0, chosen.el.scrollHeight - chosen.el.clientHeight);
    if (mode === 'top') chosen.el.scrollTop = 0;
    else if (mode === 'bottom') chosen.el.scrollTop = maxScroll;
    else if (mode === 'delta') chosen.el.scrollTop = Math.max(0, Math.min(maxScroll, chosen.el.scrollTop + Number(offset || 0)));
    else if (mode === 'position') chosen.el.scrollTop = Math.max(0, Math.min(maxScroll, Number(offset || 0)));
    chosen.el.dispatchEvent(new Event('scroll', { bubbles: true }));
    return {
      ok: true,
      mode,
      x: Math.round(chosen.x),
      y: Math.round(chosen.y),
      w: Math.round(chosen.w),
      h: Math.round(chosen.h),
      role: chosen.role,
      beforeScrollTop: Math.round(chosen.scrollTop),
      afterScrollTop: Math.round(chosen.el.scrollTop),
      maxScroll: Math.round(maxScroll)
    };
  }, { bounds, mode, offset });
}

async function findOpenDropdownBox(page, bounds = {}) {
  return page.evaluate(({ bounds }) => {
    const normalize = (s) => String(s || '')
      .replace(/[\u2192\u27f6\u2794]/g, ' -> ')
      .replace(/[\u2026]/g, '...')
      .replace(/\s+/g, ' ')
      .trim();
    function visible(el) {
      const style = window.getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
    }
    function topVisibleAt(x, y, el) {
      const top = document.elementFromPoint(Math.max(0, Math.min(window.innerWidth - 1, x)), Math.max(0, Math.min(window.innerHeight - 1, y)));
      return !!top && (el === top || el.contains(top) || top.contains(el));
    }
    const xMin = Number.isFinite(bounds.xMin) ? bounds.xMin : 0;
    const xMax = Number.isFinite(bounds.xMax) ? bounds.xMax : window.innerWidth;
    const yMin = Number.isFinite(bounds.yMin) ? bounds.yMin : 0;
    const yMax = Number.isFinite(bounds.yMax) ? bounds.yMax : window.innerHeight;
    const menuNeedles = ['today', 'tomorrow', 'yesterday', 'one week ago', 'one week from now', 'one month ago', 'one month from now', 'exact date'];
    const candidates = Array.from(document.querySelectorAll('[role="listbox"], [role="menu"], [data-testid], [class], div'))
      .filter(visible)
      .map((el) => {
        const box = el.getBoundingClientRect();
        const text = normalize(el.innerText || el.textContent || el.getAttribute('aria-label') || '');
        const lower = text.toLowerCase();
        const needleHits = menuNeedles.filter((needle) => lower.includes(needle)).length;
        const centerX = box.x + box.width / 2;
        const centerY = box.y + Math.min(Math.max(24, box.height / 2), box.height - 12);
        return {
          el,
          role: el.getAttribute('role') || '',
          text,
          lower,
          needleHits,
          x: box.x,
          y: box.y,
          w: box.width,
          h: box.height,
          area: box.width * box.height,
          centerX,
          centerY,
          top: topVisibleAt(centerX, centerY, el),
          scrollHeight: el.scrollHeight,
          clientHeight: el.clientHeight,
          scrollTop: el.scrollTop
        };
      })
      .filter((item) => {
        if (!item.top) return false;
        if (item.w < 80 || item.w > 760 || item.h < 40 || item.h > 720) return false;
        if (item.x > xMax + 120 || item.x + item.w < xMin - 120 || item.y > yMax + 220 || item.y + item.h < yMin - 220) return false;
        if (/help \/ quick tips|sort records|filter records|learn more about/i.test(item.lower)) return false;
        if (item.needleHits < 3) return false;
        return true;
      })
      .sort((a, b) => {
        const ar = ['listbox', 'menu'].includes(String(a.role || '').toLowerCase()) ? 0 : 1;
        const br = ['listbox', 'menu'].includes(String(b.role || '').toLowerCase()) ? 0 : 1;
        return ar - br || b.needleHits - a.needleHits || a.area - b.area || a.y - b.y;
      });
    const chosen = candidates[0];
    if (!chosen) return { ok: false, reason: 'no-open-dropdown-box-found' };
    return {
      ok: true,
      role: chosen.role,
      x: Math.round(chosen.x),
      y: Math.round(chosen.y),
      w: Math.round(chosen.w),
      h: Math.round(chosen.h),
      centerX: Math.round(chosen.centerX),
      centerY: Math.round(chosen.centerY),
      needleHits: chosen.needleHits,
      scrollHeight: Math.round(chosen.scrollHeight || 0),
      clientHeight: Math.round(chosen.clientHeight || 0),
      scrollTop: Math.round(chosen.scrollTop || 0),
      text_sample: chosen.text.slice(0, 180)
    };
  }, { bounds });
}

async function mouseWheelOpenDropdownTowardOption(page, pattern, label, bounds = {}, steps = null) {
  const attempts = [];
  let dropdown = await findOpenDropdownBox(page, bounds).catch((error) => ({ ok: false, error: String(error?.message || error) }));
  let center = dropdown.ok
    ? { x: dropdown.centerX, y: dropdown.centerY }
    : {
        x: Math.round((Number(bounds.xMin || 0) + Number(bounds.xMax || (bounds.xMin || 0) + 400)) / 2),
        y: Math.round((Number(bounds.yMin || 0) + Number(bounds.yMax || (bounds.yMin || 0) + 420)) / 2)
      };

  const wheelPlan = [
    { name: 'pre-visible', dy: 0 },
    { name: 'wheel-up-large-1', dy: -900 },
    { name: 'wheel-up-large-2', dy: -900 },
    { name: 'wheel-up-large-3', dy: -900 },
    { name: 'wheel-up-small', dy: -360 },
    { name: 'wheel-down-small', dy: 360 },
    { name: 'wheel-down-large', dy: 900 },
    { name: 'wheel-up-reset', dy: -1400 }
  ];

  for (const wheel of wheelPlan) {
    dropdown = await findOpenDropdownBox(page, bounds).catch((error) => ({ ok: false, error: String(error?.message || error) }));
    if (dropdown.ok) center = { x: dropdown.centerX, y: dropdown.centerY };
    await page.mouse.move(center.x, center.y).catch(() => {});
    if (wheel.dy) await page.mouse.wheel(0, wheel.dy).catch(() => {});
    await page.waitForTimeout(wheel.dy ? 450 : 150).catch(() => {});
    const clicked = await clickVisibleOption(page, pattern, `${label}-${wheel.name}`, bounds);
    attempts.push({ method: wheel.name, dropdown, center, clicked });
    if (clicked.ok) {
      const step = { action: label, method: `mouse-wheel-${wheel.name}`, dropdown, center, ...clicked };
      if (steps) steps.push(step);
      return { ok: true, label, method: `mouse-wheel-${wheel.name}`, dropdown, center, attempts };
    }
  }

  if (steps) steps.push({ action: label, ok: false, method: 'mouse-wheel-dropdown-search', dropdown, center, attempts });
  return { ok: false, label, method: 'mouse-wheel-dropdown-search', dropdown, center, attempts };
}

async function pressHomeEnterForOpenDropdown(page, label, steps) {
  const before = await page.evaluate(() => {
    const active = document.activeElement;
    const box = active?.getBoundingClientRect ? active.getBoundingClientRect() : null;
    return {
      active_tag: active?.tagName || '',
      active_role: active?.getAttribute?.('role') || '',
      active_text: String(active?.innerText || active?.textContent || active?.getAttribute?.('aria-label') || active?.getAttribute?.('placeholder') || '').replace(/\s+/g, ' ').trim().slice(0, 160),
      active_x: box ? Math.round(box.x) : null,
      active_y: box ? Math.round(box.y) : null,
      active_w: box ? Math.round(box.width) : null,
      active_h: box ? Math.round(box.height) : null
    };
  }).catch((error) => ({ error: String(error?.message || error) }));

  const keySteps = [];
  for (const key of ['Home', 'Enter']) {
    await page.keyboard.press(key).catch(async () => {
      // Some Airtable menus only respond after a small mouse nudge/focus settle.
      await page.waitForTimeout(100).catch(() => {});
      await page.keyboard.press(key).catch(() => {});
    });
    keySteps.push(key);
    await page.waitForTimeout(key === 'Home' ? 350 : 700).catch(() => {});
  }

  const after = await page.evaluate(() => {
    const active = document.activeElement;
    const box = active?.getBoundingClientRect ? active.getBoundingClientRect() : null;
    return {
      active_tag: active?.tagName || '',
      active_role: active?.getAttribute?.('role') || '',
      active_text: String(active?.innerText || active?.textContent || active?.getAttribute?.('aria-label') || active?.getAttribute?.('placeholder') || '').replace(/\s+/g, ' ').trim().slice(0, 160),
      active_x: box ? Math.round(box.x) : null,
      active_y: box ? Math.round(box.y) : null,
      active_w: box ? Math.round(box.width) : null,
      active_h: box ? Math.round(box.height) : null
    };
  }).catch((error) => ({ error: String(error?.message || error) }));

  const result = { ok: true, label, method: 'keyboard-home-enter', keys: keySteps, active_before: before, active_after: after };
  if (steps) steps.push({ action: label, ...result });
  return result;
}

async function pressTypeaheadEnterForOpenDropdown(page, query, label, steps) {
  if (!query) return { ok: false, label, method: 'keyboard-typeahead-enter', reason: 'missing-query' };
  await page.keyboard.type(String(query), { delay: 30 }).catch(() => {});
  await page.waitForTimeout(300).catch(() => {});
  await page.keyboard.press('Enter').catch(() => {});
  await page.waitForTimeout(700).catch(() => {});
  const result = { ok: true, label, method: 'keyboard-typeahead-enter', query: String(query) };
  if (steps) steps.push({ action: label, ...result });
  return result;
}

export async function clickOptionWithDropdownScroll(page, pattern, query, label, bounds, steps) {
  const attempts = [];
  let clicked = await clickVisibleOption(page, pattern, `${label}-visible`, bounds);
  attempts.push({ method: 'visible-option', clicked });
  if (clicked.ok) {
    if (steps) steps.push({ action: label, method: 'visible-option', ...clicked });
    return clicked;
  }

  for (const scrollAttempt of [
    { mode: 'top', offset: 0 },
    { mode: 'delta', offset: 180 },
    { mode: 'delta', offset: 180 },
    { mode: 'delta', offset: 240 },
    { mode: 'bottom', offset: 0 },
    { mode: 'top', offset: 0 }
  ]) {
    const scrolled = await scrollCandidateDropdown(page, bounds, scrollAttempt.mode, scrollAttempt.offset).catch((error) => ({ ok: false, error: String(error?.message || error), ...scrollAttempt }));
    await page.waitForTimeout(250).catch(() => {});
    clicked = await clickVisibleOption(page, pattern, `${label}-scroll-${scrollAttempt.mode}`, bounds);
    attempts.push({ method: `scroll-${scrollAttempt.mode}`, scrolled, clicked });
    if (clicked.ok) {
      if (steps) steps.push({ action: label, method: `scroll-${scrollAttempt.mode}`, scrolled, ...clicked });
      return clicked;
    }
  }

  if (query) {
    await page.keyboard.type(String(query), { delay: 15 }).catch(() => {});
    await page.waitForTimeout(500).catch(() => {});
    clicked = await clickVisibleOption(page, pattern, `${label}-typeahead`, bounds);
    attempts.push({ method: 'typeahead-visible-option', clicked });
    if (clicked.ok) {
      if (steps) steps.push({ action: label, method: 'typeahead-visible-option', ...clicked });
      return clicked;
    }
  }

  // Airtable relative-date menus can be virtualized and only respond to native wheel
  // events. Try mouse-wheel scrolling over the opened popup before keyboard fallbacks.
  const wheelClicked = await mouseWheelOpenDropdownTowardOption(page, pattern, label, bounds, steps).catch((error) => ({ ok: false, method: 'mouse-wheel-dropdown-search', error: String(error?.message || error) }));
  attempts.push({ method: 'mouse-wheel-dropdown-search', clicked: wheelClicked });
  if (wheelClicked.ok) return { ok: true, label, method: wheelClicked.method || 'mouse-wheel-dropdown-search', attempts };

  // Final non-preferred fallback only. Composite popup text may include all options even
  // when the visible scroll position is elsewhere, so never use it before real option-node
  // search and native wheel attempts. The caller's panel readback remains authoritative.
  clicked = await clickOptionFromCompositePopupText(page, pattern, `${label}-composite-popup-final`, bounds, steps).catch((error) => ({ ok: false, method: 'composite-popup-text-final', error: String(error?.message || error) }));
  attempts.push({ method: 'composite-popup-text-final', clicked });
  if (clicked.ok) {
    return { ok: true, label, method: 'composite-popup-text-final', attempts };
  }

  // Airtable's relative-date dropdown can focus the selected control/list instead of exposing
  // each option as a clean clickable DOM node. Use keyboard as a final fallback only; the
  // caller performs post-action panel readback before trusting success.
  const keyboardHomeEnter = await pressHomeEnterForOpenDropdown(page, label, steps).catch((error) => ({ ok: false, method: 'keyboard-home-enter', error: String(error?.message || error) }));
  attempts.push({ method: 'keyboard-home-enter', clicked: keyboardHomeEnter });
  if (keyboardHomeEnter.ok) return { ok: true, label, method: 'keyboard-home-enter', attempts };

  if (query) {
    const keyboardTypeahead = await pressTypeaheadEnterForOpenDropdown(page, query, label, steps).catch((error) => ({ ok: false, method: 'keyboard-typeahead-enter', error: String(error?.message || error) }));
    attempts.push({ method: 'keyboard-typeahead-enter', clicked: keyboardTypeahead });
    if (keyboardTypeahead.ok) return { ok: true, label, method: 'keyboard-typeahead-enter', attempts };
  }

  if (steps) steps.push({ action: label, ok: false, method: 'dropdown-scroll-visible-option', bounds, attempts });
  return { ok: false, label, attempts };
}
