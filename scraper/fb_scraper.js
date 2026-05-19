// fb_scraper.js — Facebook group post scraper (main entry)
// Scrapes property listing posts from Malaysian Facebook groups.
//
// Usage:  node fb_scraper.js
// Output: fb_posts_raw.json (appended, deduplicated)
//
// Modules: lib/fb_phone.js  lib/fb_expand.js  lib/fb_extract.js

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const { extractPhone } = require('./lib/fb_phone');
const { clickExpandButtons } = require('./lib/fb_expand');
const { extractPosts } = require('./lib/fb_extract');

// ============================================================
// CONFIGURATION — edit here to add groups or update cookies
// ============================================================

const COOKIES = [
  { name: 'c_user', value: '100000390330536', domain: '.facebook.com', path: '/' },
  { name: 'xs', value: '22%3ABP076DDNtD7PnQ%3A2%3A1773550824%3A-1%3A-1%3A%3AAcw-mSgGoEFZAI_4rPrQWnZdsDrepQ1MED6H7hony9w', domain: '.facebook.com', path: '/' },
  { name: 'fr', value: '11lkkMhtF2En5XJeD.AWeKxawEKCkeI_s_RFZZDjCg3hFSAcCmvKx2epfkf63Jt-qXC_U.BqAmQE..AAA.0.0.BqAmQE.AWcmtemPt2EE7myVwQ5QLmlSAr0', domain: '.facebook.com', path: '/' },
  { name: 'presence', value: 'C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1778541574416%2C%22v%22%3A1%7D', domain: '.facebook.com', path: '/' },
];

const GROUPS = [
  { id: '1467428250213843', name: 'JB新山租房与出租' },
  { id: '1313487628797877', name: 'Group2' },
  { id: '801784763175081',   name: 'Group3-房屋出租' },
  { id: 'JBPropertyForSalesRent', name: 'JB Property For Sales/Rent' },
  { id: '290627785937141',   name: 'Group5-租屋' },
];

const DATA_DIR = '/home/user/fb_data/';
const OUTPUT_JSON = DATA_DIR + 'fb_posts_raw.json';

// ============================================================
// HELPERS
// ============================================================

async function launchBrowser() {
  return chromium.launch({ headless: true });
}

function isBrowserDeadError(errMsg) {
  // FB anti-bot / session kill closes the browser or page
  return /(?:Target|browser|context).*(?:closed|been closed)/i.test(errMsg || '');
}

// ============================================================
// SCRAPER
// ============================================================

async function scrapeGroup(browser, groupId, groupName) {
  console.log(`[${groupName}] 开始抓取...`);

  let context = null;
  let page = null;
  const posts = [];

  try {
    context = await browser.newContext({
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      locale: 'zh-CN', viewport: { width: 1280, height: 900 },
    });
    await context.addCookies(COOKIES);
    page = await context.newPage();

    // 1. Navigate & wait
    await page.goto(`https://www.facebook.com/groups/${groupId}`, {
      waitUntil: 'domcontentloaded', timeout: 20000
    });
    await page.waitForTimeout(2000);

    try {
      await page.waitForSelector('[role="article"]', { timeout: 10000 });
    } catch (e) {
      console.log(`[${groupName}] No articles within 10s, continuing`);
    }

    // 2. Scroll to load posts
    let articleCount = 0, lastCount = 0;
    for (let i = 0; i < 10; i++) {
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForTimeout(1500);
      articleCount = await page.evaluate(() =>
        document.querySelectorAll('[role="article"]').length
      );
      if (articleCount === lastCount && i > 4) break;
      lastCount = articleCount;
    }

    // 3. Extract BEFORE expanding (reliable baseline)
    console.log(`[${groupName}] 数据处理中...`);
    const preExpandPosts = await extractPosts(page, groupId);

    // 4. Click all expand buttons
    const expandClicked = await clickExpandButtons(page);
    await page.waitForTimeout(2000);

    // 5. Extract AFTER expanding (preferred — longer text)
    const postExpandPosts = await extractPosts(page, groupId);

    // 6. Merge: post-expand first (preferred), pre-expand fill gaps
    const seenLinks = new Set();
    for (const p of postExpandPosts) {
      if (p.postLink) seenLinks.add(p.postLink);
      posts.push(buildPost(groupId, groupName, p));
    }
    for (const p of preExpandPosts) {
      if (p.postLink && seenLinks.has(p.postLink)) continue;
      if (p.postLink) seenLinks.add(p.postLink);
      posts.push(buildPost(groupId, groupName, p));
    }

    console.log(`[${groupName}] 结束: ${articleCount} articles, ${preExpandPosts.length}/${postExpandPosts.length} pre/post, ${expandClicked} expands -> ${posts.length} posts`);
  } catch (e) {
    console.error(`[${groupName}] Error: ${e.message}`);
    // Re-throw browser-dead errors so main loop can re-launch
    if (isBrowserDeadError(e.message)) throw e;
  } finally {
    try { if (page) await page.close().catch(() => {}); } catch (_) {}
    try { if (context) await context.close().catch(() => {}); } catch (_) {}
  }
  return posts;
}

function buildPost(groupId, groupName, p) {
  return {
    group_id: groupId,
    group_name: groupName,
    agent_name: p.agentName,
    text: p.text.substring(0, 3000),
    phone: extractPhone(p.text),
    link: p.postLink || `https://www.facebook.com/groups/${groupId}`,
    photos: [],
    scraped_at: new Date().toISOString()
  };
}

// ============================================================
// MAIN
// ============================================================

(async () => {
  console.log('[scraper] 开始');
  fs.mkdirSync(DATA_DIR, { recursive: true });

  let allPosts = [];
  let browser = null;

  for (let gi = 0; gi < GROUPS.length; gi++) {
    const g = GROUPS[gi];
    try {
      // Ensure live browser
      if (!browser) {
        browser = await launchBrowser();
      }

      const groupPosts = await scrapeGroup(browser, g.id, g.name);
      allPosts = allPosts.concat(groupPosts || []);
    } catch (e) {
      // Browser died → close it, re-launch, retry this group once
      if (isBrowserDeadError(e.message)) {
        console.error(`[${g.name}] Browser dead, re-launching...`);
        try { if (browser) await browser.close().catch(() => {}); } catch (_) {}
        browser = null;

        // Retry once with fresh browser
        try {
          browser = await launchBrowser();
          const retryPosts = await scrapeGroup(browser, g.id, g.name);
          allPosts = allPosts.concat(retryPosts || []);
          console.error(`[${g.name}] Retry OK`);
        } catch (e2) {
          console.error(`[${g.name}] Retry also failed: ${e2.message}`);
          try { if (browser) await browser.close().catch(() => {}); } catch (_) {}
          browser = null;
        }
      } else {
        console.error(`[${g.name}] Fatal: ${e.message}`);
      }
    }
  }

  // Final cleanup
  try { if (browser) await browser.close().catch(() => {}); } catch (_) {}

  if (allPosts.length === 0) {
    console.log(JSON.stringify({ error: 'no posts' }));
    process.exit(0);
  }

  // Dedup + append
  let existing = [];
  try {
    existing = JSON.parse(fs.readFileSync(OUTPUT_JSON, 'utf-8'));
  } catch (e) { /* first run */ }

  const existingKeys = new Set(existing.map(p => p.text?.substring(0, 80)));
  const newPosts = allPosts.filter(p => !existingKeys.has(p.text?.substring(0, 80)));
  const merged = [...existing, ...newPosts];
  fs.writeFileSync(OUTPUT_JSON, JSON.stringify(merged, null, 2), 'utf-8');

  console.log('[scraper] 结束');
  console.log(JSON.stringify({
    total: merged.length,
    new: newPosts.length,
    groups: GROUPS.map(g => ({
      name: g.name,
      posts: allPosts.filter(p => p.group_id === g.id).length
    }))
  }));
  process.exit(0);
})();
