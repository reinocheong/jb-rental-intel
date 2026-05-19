const fs = require('fs');
const { extractPhone } = require('./lib/fb_phone');
const { clickExpandButtons } = require('./lib/fb_expand');
const { extractPosts } = require('./lib/fb_extract');
const { launchBrowser, isBrowserDeadError } = require('./lib/browser');

const COOKIES = [{ name: 'c_user', value: '100000390330536', domain: '.facebook.com', path: '/' }, { name: 'xs', value: '22%3ABP076DDNtD7PnQ%3A2%3A1773550824%3A-1%3A-1%3A%3AAcw-mSgGoEFZAI_4rPrQWnZdsDrepQ1MED6H7hony9w', domain: '.facebook.com', path: '/' }, { name: 'fr', value: '11lkkMhtF2En5XJeD.AWeKxawEKCkeI_s_RFZZDjCg3hFSAcCmvKx2epfkf63Jt-qXC_U.BqAmQE..AAA.0.0.BqAmQE.AWcmtemPt2EE7myVwQ5QLmlSAr0', domain: '.facebook.com', path: '/' }, { name: 'presence', value: 'C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1778541574416%2C%22v%22%3A1%7D', domain: '.facebook.com', path: '/' }];
const GROUPS = [{ id: '1467428250213843', name: 'JB新山租房与出租' }, { id: '1313487628797877', name: 'Group2' }, { id: '801784763175081', name: 'Group3-房屋出租' }, { id: 'JBPropertyForSalesRent', name: 'JB Property For Sales/Rent' }, { id: '290627785937141', name: 'Group5-租屋' }];
const OUTPUT_JSON = '/home/user/fb_data/fb_posts_raw.json';

async function scrapeGroup(browser, groupId, groupName) {
  console.log(`[scraper/fb_scraper.js][${groupName}] 开始抓取`);
  let context = null, page = null, posts = [];
  try {
    context = await browser.newContext({ userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', locale: 'zh-CN' });
    await context.addCookies(COOKIES); page = await context.newPage();
    await page.goto(`https://www.facebook.com/groups/${groupId}`, { waitUntil: 'domcontentloaded', timeout: 20000 });
    const pre = await extractPosts(page, groupId); await clickExpandButtons(page); const post = await extractPosts(page, groupId);
    const seen = new Set();
    post.forEach(p => { if(p.postLink) seen.add(p.postLink); posts.push(buildPost(groupId, groupName, p)); });
    pre.forEach(p => { if(!seen.has(p.postLink)) posts.push(buildPost(groupId, groupName, p)); });
    console.log(`[scraper/fb_scraper.js][${groupName}] 结束: 抓取到 ${posts.length} 条`);
  } catch (e) {
    fs.appendFileSync('/home/user/jb-rental-intel/.logs/error.log', `[${new Date().toISOString()}] [scraper/fb_scraper.js] [L22] -> ${e.stack}\n`);
    if (isBrowserDeadError(e.message)) throw e;
  } finally { if(page) await page.close(); if(context) await context.close(); }
  return posts;
}

function buildPost(groupId, groupName, p) {
  return { group_id: groupId, group_name: groupName, agent_name: p.agentName, text: p.text.substring(0, 3000), phone: extractPhone(p.text), link: p.postLink || `https://www.facebook.com/groups/${groupId}`, scraped_at: new Date().toISOString() };
}

(async () => {
  console.log('[scraper/fb_scraper.js][main] 开始');
  let allPosts = [], browser = null;
  for (const g of GROUPS) {
    try {
      if (!browser) browser = await launchBrowser();
      const p = await scrapeGroup(browser, g.id, g.name); allPosts = allPosts.concat(p || []);
    } catch (e) {
      if (browser) await browser.close(); browser = null;
    }
  }
  if (browser) await browser.close();
  if (allPosts.length > 0) fs.writeFileSync(OUTPUT_JSON, JSON.stringify(allPosts, null, 2));
  console.log('[scraper/fb_scraper.js][main] 结束');
})();
