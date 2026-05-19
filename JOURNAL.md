# JOURNAL.md — 开发流水账

## 2026-05

- **2026-05-13 [AI]**
  - 修复推广 cron 缺少 `--send` 参数导致干跑不发送的问题。
- **2026-05-14 [AI]**
  - 重写 `architecture.html` 为纯文字流程图，优化手机端浏览体验。
  - 重写推广文案 A/B 为 cobroke 定位，并上线交替发送机制。
  - 上线 `rentals.html` 与 `export_rentals_json.py`，实现房源卡片式手机浏览。
  - 重写 `clean_post_text()`，增加 15 条正则过滤 FB 界面噪音。
  - 增强 `extract_rent()`，支持回填租金数据。
  - 引入 `extract_listing_type()` 价格阈值逻辑，区分出售与出租。
  - 过滤 FB 匿名用户名（如 ThrillingGrapefruit）。
  - 修复 Agent 名与时间粘连的问题。
  - 美化 Google Sheets 格式。
- **2026-05-15 [AI]**
  - 上线 `auth_server.py` 与 Cloudflare Tunnel，加入 Google 登录验证。
  - `rentals.html` 接入登录系统，并自动显示 Stripe 付款页。
  - 实现 `auto_sync_tunnel.sh` 自动同步隧道 URL 到 `rentals.html`。
  - 更新所有推广链接指向 `rentals.html`。
- **2026-05-16 [AI]**
  - 优化运行成本：除隧道同步外，所有任务切为 `no_agent=true` 纯脚本模式。
- **2026-05-18 [AI]**
  - 重构 `fb_scraper.js`：全局复用浏览器，增加 try/catch 容错与超时保护。
  - 拆分 cron 任务：将爬虫与解析器错开运行，解决 120s 超时报错。
- **2026-05-19 [AI]**
  - 启动 `AI_ARCHITECT_PROTOCOL` 规范化整改。
  - 补齐 SSOT 文档：`USER.md`, `JOURNAL.md`, `MEMORY.md`。
  - 建立 Git 版本控制安全基线。
