import { ensureDir } from '../../shared/dcoir_ui_common.mjs';
import { log } from './airtable_wbs09_ui_config_one_view_runtime.mjs';

export async function openAirtablePage(chromium, args, baseUrl) {
  let browser = null;
  let context = null;
  let page = null;
  let closeMode = 'launched';

  if (args.connectCdpUrl) {
    closeMode = 'cdp_disconnect_only';
    log('Connecting to existing Chrome over CDP.', { connect_cdp_url: args.connectCdpUrl });
    browser = await chromium.connectOverCDP(args.connectCdpUrl);
    context = browser.contexts()[0];
    if (!context) throw new Error('CDP connection succeeded but no browser context was available.');
    page = context.pages()[0] || await context.newPage();
  } else if (args.userDataDir) {
    closeMode = 'persistent_context';
    log('Launching persistent browser context.', { user_data_dir: args.userDataDir, chrome_channel: Boolean(args.useChromeChannel) });
    ensureDir(args.userDataDir);
    context = await chromium.launchPersistentContext(args.userDataDir, {
      headless: Boolean(args.headless),
      channel: args.useChromeChannel ? 'chrome' : undefined,
      viewport: { width: 1440, height: 1000 }
    });
    browser = context.browser();
    page = context.pages()[0] || await context.newPage();
  } else {
    log('Launching browser context.', { chrome_channel: Boolean(args.useChromeChannel) });
    browser = await chromium.launch({ headless: Boolean(args.headless), channel: args.useChromeChannel ? 'chrome' : undefined });
    context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    page = await context.newPage();
  }

  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  return { browser, context, page, closeMode };
}

export async function closeAirtablePage(context, browser, closeMode) {
  if (context && closeMode === 'persistent_context') await context.close();
  else if (browser) await browser.close();
}
