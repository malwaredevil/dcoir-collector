import { chromium } from 'playwright';
import { safeMousePark } from '../../shared/dcoir_airtable_ui_geometry.mjs';

export async function openBrowser(args, baseUrl) {
  let browser = null;
  let context = null;
  let page = null;
  let closeMode = 'launched';

  if (args.connectCdpUrl) {
    browser = await chromium.connectOverCDP(args.connectCdpUrl);
    context = browser.contexts()[0] || await browser.newContext();
    page = context.pages()[0] || await context.newPage();
    closeMode = 'cdp';
  } else if (args.userDataDir) {
    context = await chromium.launchPersistentContext(args.userDataDir, {
      headless: args.headless,
      channel: args.useChromeChannel ? 'chrome' : undefined,
      viewport: { width: 1500, height: 980 }
    });
    page = context.pages()[0] || await context.newPage();
    closeMode = 'persistent';
  } else {
    browser = await chromium.launch({ headless: args.headless, channel: args.useChromeChannel ? 'chrome' : undefined });
    context = await browser.newContext({ viewport: { width: 1500, height: 980 } });
    page = await context.newPage();
    closeMode = 'launched';
  }

  await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForLoadState('networkidle', { timeout: 12000 }).catch(() => {});
  await safeMousePark(page, 'after-open-base-url');
  return { browser, context, page, closeMode };
}

export async function closeBrowser(browserState, args, success, rl) {
  const { browser, context, closeMode } = browserState || {};
  if (!success && args.keepBrowserOpenOnFailure) {
    console.error('Failure detected. Browser will remain open for inspection. Press Enter in PowerShell after you finish inspecting/uploading screenshots.');
    if (rl) await rl.question('');
    return;
  }
  if (closeMode === 'persistent' && context) await context.close().catch(() => {});
  else if (browser) await browser.close().catch(() => {});
}
