const { chromium } = require('playwright');

async function launchBrowser() {
  console.log('[scraper/lib/browser.js][init] 启动浏览器');
  return chromium.launch({ headless: true });
}

function isBrowserDeadError(errMsg) {
  return /(?:Target|browser|context).*(?:closed|been closed)/i.test(errMsg || '');
}

module.exports = { launchBrowser, isBrowserDeadError };
