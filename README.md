# Smart Tenancy Pro — JB 房产数据 SaaS

> 从 FB 抓取 agent 号码 → WhatsApp 自动推广 → Google 登录试用 → Stripe 付费续费，全链路自动化。

---

## 一句话看懂

```
FB 群组帖子 ──→ 提取 agent 电话 ──→ WhatsApp 推广 ──→ Google 登录试用 ──→ RM 9.90/月自动续费
     ↑ scraper/          ↑ processors/       ↑ outreach/      ↑ rentals.html    ↑ stripe_checker.py
```

> ✅ 全链路已跑通。客户打开 rentals.html → Google 登录 → 立即看数据，不用填表。

---

## 目录结构

```
/home/user/jb-rental-intel/          ← ★ 项目根目录
│
├── 📄 文档（根目录）
│   ├── README.md                    ← 本文档
│   └── DEPLOY.md                    ← 部署手册 + cron 表 + 故障排查
│
├── 📄 docs/                         ← 详细文档
│   ├── ARCHITECTURE.md              ← 架构全景 & 关键决策
│   ├── SHEETS.md                    ← Google Sheets 总清单
│   ├── WORKFLOW.md                  ← 完整五阶段工作流（日常操作看这个）
│   ├── TODO.md                      ← 进度表
│   ├── AI_ARCHITECT_PROTOCOL.md     ← 开发协议（最高准则）
│   ├── 推广文案.md                   ← A/B 推广文案
│   ├── 推广计划.md                   ← 推广引擎设计方案
│   └── architecture.html            ← 架构图（手机端纯文字流程图，无SVG）
│
├── rentals.html                    ← 📱 房源浏览页（Google 登录，落地页+数据页一体）
│
├── 🔧 scraper/                      ← 阶段①：FB 爬虫
│   ├── fb_scraper.js                # 主入口（166行）
│   └── lib/
│       ├── fb_phone.js              # 电话号码提取（45行）
│       ├── fb_expand.js             # 展开按钮点击（78行）
│       └── fb_extract.js            # 帖子文本提取（56行）
│
├── 🔧 processors/                   ← 阶段②：数据解析
│   ├── fb_parser.py                 # ★ 主路径 → Google Sheets（含楼盘名标准化 + 电话规范化）
│   ├── process_fb.py                # 备用 → Excel
│   └── process_posts.py             # 旧版（不推荐）
│
├── scripts/                      ← 维护脚本
│   ├── clean_property_names.py      # ★ 一次性清洗：Property Name 标准化 + 去垃圾
│   ├── clean_phones.py              # ★ 一次性清洗：Phone 格式统一为 +60 国际
│   ├── beautify_sheet.py            # Sheet 格式化
│   ├── export_rentals_json.py       # 导出 JSON
│   └── auto_sync_tunnel.sh          # ★ 隧道 URL 自动同步（每5分钟，静默）
│
├── 📱 wa/                           ← WhatsApp 通信栈
│   ├── wa_daemon.js                 # Baileys 长连接（:3456，24/7）
│   ├── wa_notify.js                 # CLI 发送封装（84行）
│   └── wa_listener.js               # 回复监听 & 状态更新
│
├── 🚀 outreach/                     ← 阶段③：WhatsApp 推广引擎
│   ├── outreach_engine.py           # ★ 主入口（分时段发送，动态配额）
│   ├── notify_subscribers.py        # 订阅通知推送（9/13/18点）
│   ├── agent_phones.txt             # 手动整理备份清单
│   └── lib/
│       ├── wa_sender.py             # WhatsApp 发送 + 模板A
│       ├── cooldown_filter.py       # 30天冷却 + 动态配额计算
│       ├── sheets_tracker.py        # 读取内部 Sheet Agent List + 读写推广记录
│       └── maintain_agents.py       # Agent List 每日去重维护（139人）
│
├── 💳 根目录脚本                     ← 阶段④⑤：订阅 & 付费
│   ├── sub_mgr.py                   # ★ 订阅管理器（703行，8种命令）
│   ├── stripe_checker.py            # Stripe 付款检测（79行）
│   ├── subscribers.db               # SQLite 订阅数据库
│   ├── .form_processed.json         # 已处理注册去重
│   ├── processed_payments.txt       # 已处理 Stripe 付款去重
│   └── .env                         # Stripe Secret Key（不提交 Git）
│
├── 🗂️ scripts/                     ← 辅助脚本
│   ├── summary_report.py            # 每4小时运行状态汇总（8/12/16/20点）
│   ├── build_calendar.py
│   ├── update_calendar.py
│   ├── fix_xlsx_add_column.py
│   └── migrate_mspro_to_sheets.py
│
├── 📦 wa_session/                   ← Baileys 认证状态
├── 📦 archived/                     ← 旧版归档
├── 📦 node_modules/                 ← Node.js 依赖
├── 📦 .logs/                        ← 日志目录
│
├── 📄 根目录文件
│   ├── package.json                 ← Node.js 依赖配置
│   ├── package-lock.json
│   ├── index.html                   ← 落地页（reinocheong.github.io/jb-rental-intel/）
│   ├── architecture.html            ← 架构图（GitHub Pages 部署副本）
│   ├── rentals.html                 ← ★ 房源浏览页（手机端卡片式，搜楼盘/agent/户型）
│   └── gen-lang-client-xxx.json     ← Google Service Account Key
│
├── 🗂️ scripts/
│   ├── export_rentals_json.py       ← ★ 导出 JB Rentals Sheet → JSON（只读不写）
│   ├── ...
│
├── 📁 data/
│   └── rentals.json                 ← JB Rentals 房源数据（每30分钟自动更新，Git追踪）

外部数据（不在项目中，脚本读写）：
  /home/user/fb_data/fb_posts_raw.json     ← 爬虫输出
  /home/user/fb_data/fb_rentals.xlsx       ← Excel 输出
  /home/user/fb_photos/                    ← 图片缓存
```

---

## 五阶段对应脚本速查

| 阶段 | 脚本 | 路径 | 执行命令 |
|:----:|------|------|----------|
| ① | FB 爬虫 | `scraper/fb_scraper.js` | `cd scraper && node fb_scraper.js` |
| ② | 解析入 Sheet | `processors/fb_parser.py` | `cd processors && python3 fb_parser.py` |
| ③ | 推广引擎 | `outreach/outreach_engine.py` | `python3 outreach/outreach_engine.py --send --slot 1 --total-slots 5` |
| ③ | Agent List 维护 | `outreach/lib/maintain_agents.py` | `python3 outreach/lib/maintain_agents.py` |
| ③ | 订阅通知推送 | `outreach/notify_subscribers.py` | `python3 outreach/notify_subscribers.py <morning\|afternoon\|evening>` |
| ④ | 订阅管理器 | `sub_mgr.py` | `python3 sub_mgr.py <命令>` |
| ⑤ | Stripe 检测 | `stripe_checker.py` | 通过 `sub_mgr.py stripe-check` 调用 |
| 📱 | WhatsApp Daemon | `wa/wa_daemon.js` | `node wa/wa_daemon.js` |
| 📱 | WhatsApp 发送 | `wa/wa_notify.js` | `node wa/wa_notify.js send <phone> <msg>` |
| 📊 | 状态汇总 | `scripts/summary_report.py` | `python3 scripts/summary_report.py` |

## 每日自动运行表

| 时间 | 任务 | 通知 |
|:----:|------|:----:|
| 每30分 | ① 爬虫抓帖 + ② 解析入 Sheet | 静默 |
| 每30分 | 📋 rentals.json 自动导出 → git push | 静默 |
| 每5分 | 🔐 隧道 URL 自动同步（检测变化→更新→push） | 静默 |
| 每5分 | ④ Form 检查 → 自动开试用 | 静默 |
| 每30分 | ⑤ Stripe 付款检测 + 到期回收 | 静默 |
| 10:00 | ③ Agent List 更新（去重139人） | ✅ |
| 10:30 | ③ 推广时段①（1人） | ✅ |
| 11:30 | ③ 推广时段②（1人） | ✅ |
| 12:00 | 📊 状态汇总 | ✅ |
| 12:30 | ③ 推广时段③（1人） | ✅ |
| 13:30 | ③ 推广时段④（1人） | ✅ |
| 14:30 | ③ 推广时段⑤（1人） | ✅ |
| 9:00 | ④ 试用到期提醒 | ✅ |
| 13:00 | 通知推送·午间 | ✅ |
| 18:00 | 通知推送·日报 | ✅ |

> **动态配额：** 每日推广人数 = max(2, min(10, 剩余未推广Agent ÷ 30 + 1))  
> **防封策略：** 分5个时段（10:30-14:30），每时段只发1人，不集中发送

---

## 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| JavaScript | `snake_case.js` | `fb_scraper.js`, `wa_daemon.js` |
| Python | `snake_case.py` | `sub_mgr.py`, `fb_parser.py` |
| 函数 | `camelCase` | `scrapeGroup()`, `extractPhone()` |
| 常量 | `UPPER_SNAKE` | `COOKIES`, `GROUPS`, `DATA_DIR` |

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 爬虫 | Node.js + Playwright (headless Chromium) |
| 解析器 | Python 3.12, openpyxl, googleapiclient |
| WhatsApp | @whiskeysockets/baileys (WebSocket 长连接) |
| 支付 | Stripe API (live key) |
| 订阅管理 | Python 3.12 + SQLite |
| 认证 | Facebook Cookies, Google Service Account |
| 落地页 | 纯 HTML/CSS, GitHub Pages |
| 调度 | Hermes Agent cron |

---

## 快速决策

| 要做的事 | 操作什么文件 |
|----------|-------------|
| 加 FB 群组 | `scraper/fb_scraper.js` → `GROUPS` 数组 |
| 换 FB Cookie | `scraper/fb_scraper.js` → `COOKIES` 数组 |
| 支持新电话格式 | `scraper/lib/fb_phone.js` → `patterns` 数组 |
| 加新楼盘名 | `processors/fb_parser.py` → `KNOWN_PROPERTIES` 列表 |
| 改推广文案 | `docs/推广文案.md` + 更新 `outreach/lib/wa_sender.py` |
| 改订阅价格 | `sub_mgr.py` 中提醒文案的 Stripe 链接 |
| 查订阅者 | `python3 sub_mgr.py list` |
| 手动开试用 | `python3 sub_mgr.py trial <email> <name> standard <phone>` |
| 启动 WhatsApp | `node wa/wa_daemon.js`（常驻后台） |
| 手动推送通知 | `python3 outreach/notify_subscribers.py <morning\|afternoon\|evening\|test>` |

> 📘 完整部署、cron 表、故障排查 → **[DEPLOY.md](DEPLOY.md)**  
> 📘 架构全景 & 决策记录 → **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**  
> 📘 Google Sheets 总清单 → **[docs/SHEETS.md](docs/SHEETS.md)**  
> 📘 五阶段完整流程 → **[docs/WORKFLOW.md](docs/WORKFLOW.md)**

---

## 修复记录

| 日期 | 问题 | 修复 |
|------|------|------|
| 2026-05-13 | 推广 cron prompt 缺少 `--send` 参数，LLM 有时跑干跑不发送 | 5个outreach cron prompt 全部显式加上 `--send --slot X --total-slots 5` |
| 2026-05-14 | architecture.html 手机端浏览体验差（SVG缩放文字看不清，需左右滑动） | 完全重写为纯文字流程图，手机端上下滚动浏览，移除SVG |
| 2026-05-14 | 推广文案A回复率0%，定位偏差 | 重写文案A/B为cobroke定位，outreach_engine A/B交替发送 |
| 2026-05-14 | 客户看Sheet裸数据体验差（12列×400行，手机难浏览） | 新建 rentals.html + export_rentals_json.py，每30分导出JSON，卡片式手机浏览 |
| 2026-05-14 | rentals.html 初版太「程序员风」，不美观 | 完全重写：彩色accent条、pill标签、NEW徽章、头像、骨架屏、毛玻璃header |
| 2026-05-14 | 4个cron同时做rentals导出，git push冲突报错 | 删掉3个重复cron + 1个重复脚本，保留唯一入口 |
| 2026-05-14 | Post Text 塞满FB界面噪音（火速回复、赞评论分享、展开+NM） | 重写 clean_post_text()，加15条正则，706行变干净 |
| 2026-05-14 | 209条出租帖 Rent 列为空，帖文里明明有价钱 | 重写 extract_rent()（支持RM1.2k、MYR、raw text），回填41条；169条原文无价无法提取 |
| 2026-05-14 | 出售帖误判为出租 | extract_listing_type() 加价格阈值（>50k + 无rent上下文→出售） |
| 2026-05-14 | Agent名出现FB随机用户名（ThrillingGrapefruit、AmbitiousMouse6348） | fb_extract.js + fb_parser.py 双端过滤，清洗31个 |
| 2026-05-14 | Post Text 里 agent 名粘时间（Fion Foo34分钟） | clean_post_text() 加时间粘连正则，384行修复 |
| 2026-05-14 | Sheet 裸数据难阅读 | 纯格式美化：冻结表头、斑马条纹、条件颜色、列宽调整（不改数据，Ctrl+Z可撤销） |
| 2026-05-15 | rentals.html 公开 URL 无登录，数据可被任何人获取 | 新增 auth_server.py + Cloudflare Tunnel，加入 Google 登录页（首次登录自动开通 3 天试用） |
| 2026-05-15 | 到期用户无付款入口 | rentals.html 加 Stripe 付款页（到期自动显示） |
| 2026-05-15 | Cloudflare Tunnel 每次重启 URL 变化，rentals.html 登录失效 | `auto_sync_tunnel.sh` 每5分钟检测 `/tmp/cf_active_url.txt`，变化即更新 `rentals.html` → commit → push，全程静默 |
| 2026-05-15 | WA 推广 + 通知仍指向旧 Form / Sheet 链接 | 全链路 URL 切换至 rentals.html，文案更新为 Google 登录 |
| 2026-05-14 | Phone 列格式混乱（012本地/60无+/同号双份/遮罩垃圾） | `clean_phones.py` 一次性清洗 471→+60，`fb_parser.py` 新增 `normalize_phone()` 自动标准 |