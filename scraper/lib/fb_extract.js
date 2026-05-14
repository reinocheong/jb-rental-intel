// fb_extract.js — Extract post data from Facebook group page
// Finds all [role="article"] elements, extracts text, agent name, and post link.

/**
 * Extract posts from the current page state.
 * Filters out posts shorter than 40 chars and known spam patterns.
 *
 * @param {import('playwright').Page} page
 * @param {string} groupId
 * @returns {Promise<Array<{agentName: string, text: string, postLink: string}>>}
 */
async function extractPosts(page, groupId) {
  return page.evaluate((gid) => {
    const articles = document.querySelectorAll('[role="article"]');
    const results = [];

    // FB generated username: two+ CamelCase words glued together
    // e.g. AmbitiousMouse6348, ThrillingGrapefruit, RelaxingDachshund5812Rnf
    const isFbGeneratedName = (name) => /^[A-Z][a-z]{3,}[A-Z][a-z]{3,}\d*$/.test(name);

    // Try to find a real name in the post text (Chinese or English)
    const findRealName = (text) => {
      // Chinese name: 2-4 Chinese chars near start
      const m = text.match(/^.{0,30}?([\u4e00-\u9fff]{2,4})(?:\s*[·火速关注])/);
      if (m) return m[1];
      // English name: Capitalized First Last
      const m2 = text.match(/(?:^|\s)([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)(?:\s*\d)/);
      if (m2 && !isFbGeneratedName(m2[1])) return m2[1];
      return '';
    };

    for (const article of articles) {
      const text = (article.textContent || '').trim();

      // Skip too-short posts and known spam
      if (text.length < 40) continue;
      if (/^你的\d+年wira/.test(text)) continue;

      // Extract agent name
      let agentName = '';
      const m = text.match(/^([^\d•·\s]{2,30}?)(?:\d|·|小时|分钟|天|周|月|年|赞|关注)/);
      if (m) agentName = m[1].trim();

      // Filter FB generated usernames — try to find real name instead
      if (agentName && isFbGeneratedName(agentName)) {
        const real = findRealName(text);
        agentName = real || '';  // empty = let Python parser try
      }

      // Extract Facebook post permalink
      let postLink = '';
      for (const link of article.querySelectorAll('a')) {
        const href = link.href || '';
        const pm = href.match(/\/(posts|permalink)\/(\d{6,})/);
        if (pm) {
          postLink = `https://www.facebook.com/groups/${gid}/posts/${pm[2]}`;
          break;
        }
      }
      // Fallback: try shorter post ID pattern
      if (!postLink) {
        for (const link of article.querySelectorAll('a')) {
          const pm = (link.href || '').match(/\/posts\/(\d+)/);
          if (pm) {
            postLink = `https://www.facebook.com/groups/${gid}/posts/${pm[1]}`;
            break;
          }
        }
      }

      results.push({ agentName, text, postLink });
    }
    return results;
  }, groupId);
}

module.exports = { extractPosts };
