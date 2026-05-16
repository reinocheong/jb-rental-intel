# DEPLOY.md — 部署与环境手册

> 项目：Smart Tenancy Pro — JB 房产数据 SaaS  
> 根目录：`/home/user/jb-rental-intel/`  
> 最后更新：2026-05-15

---

## 运行环境

| 项目 | 值 |
|------|-----|
| 操作系统 | WSL Ubuntu (Windows Subsystem for Linux) |
| Node.js | v22.22.2 |
| Python | 3.11 (Hermes Agent venv) / 3.12 (系统) |
| Playwright | chromium headless shell 已安装 |
| Baileys | `@whiskeysockets/baileys` 已安装 |
| 工作目录 | `/home/user/jb-rental-intel/` |

---

## 环境变量

`.env` 文件（根目录，不提交 Git）：

```bash
STRIPE_SECRET_KEY=sk_live_...
```

---

## 依赖安装

```bash
cd /home/user/jb-rental-intel

# Node.js 依赖（scraper + WhatsApp）
npm install
# 包含: playwright, @whiskeysockets/baileys

# Playwright 浏览器
npx playwright install chromium

# Python 依赖
pip install google-auth google-api-python-client stripe
```

---

## 启动服务

### Auth Server + Cloudflare Tunnel

```bash
bash auth/start_auth.sh
```

启动后 HTTPS 隧道 URL 保存在 `/tmp/cf_active_url.txt`。

### WhatsApp Daemon

```bash
bash wa/start_daemon.sh
```

### @reboot 自启（已配置）

```bash
@reboot bash /home/user/jb-rental-intel/auth/start_auth.sh
@reboot bash /home/user/jb-rental-intel/wa/start_daemon.sh
```

### 1. WhatsApp Daemon（必须 24/7 常驻）

```bash
cd /home/user/jb-rental-intel

# 启动（首次会生成 QR 码扫码登录）
node wa/wa_daemon.js

# 或后台运行
nohup node wa/wa_daemon.js > .logs/wa_daemon.log 2>&1 &
```

### 2. FB 爬虫（手动运行）

```bash
cd /home/user/jb-rental-intel/scraper
node fb_scraper.js
```

### 3. 解析器（手动运行）

```bash
cd /home/user/jb-rental-intel/processors
python3 fb_parser.py
```

## 推广引擎（每天 10:30-14:30 cron 自动跑）

### A/B 测试（2026-05-14 上线）

outreach_engine 奇偶交替发送文案A/B，推广记录 Sheet「模板」列记录。

| 模板 | 定位 | 核心卖点 |
|------|------|----------|
| A | 同行共鸣 | 不用翻群找cobroke，全部agent房源在Sheet里 |
| B | 价值优先 | 搜楼盘名→5秒找到对应agent→WhatsApp谈合作 |

### 手动运行（需 wa_daemon 在线）

```bash
cd /home/user/jb-rental-intel

# 干跑验证（不发送）
python3 outreach/outreach_engine.py

# 正式发送（需 wa_daemon 在线）
python3 outreach/outreach_engine.py --send

# 自定义数量
python3 outreach/outreach_engine.py --send --limit 3
```

---

## 房源浏览页（rentals.html）

### 数据导出脚本

```bash
cd /home/user/jb-rental-intel

# 手动导出（从 JB Rentals Sheet 读数据→JSON，只读不写）
python3 scripts/export_rentals_json.py
# 输出: data/rentals.json (697+条房源)
```

### 自动更新（每30分钟）

Cron 每 30 分钟跑 `scripts/export_rentals_json.py`，仅导出到本地 `data/rentals.json`（不再公开推送）。
数据通过 auth_server 按需提供 — 用户登录后动态获取。

### 登录机制（2026-05-15 新增）

- **登录页**：打开 URL 先看到登录页（暗色主题卡片式），输入邮箱+密码
- **后端**：`auth/auth_server.py`（Python HTTP）验证凭据 → 查内部运营 Sheet「授权用户」tab
- **隧道**：通过 Cloudflare Tunnel 暴露公网 HTTPS
- **Token**：24h 有效，存 localStorage，登录后无需重复输入
- **用户管理**：在内部运营 Sheet →「授权用户」tab 加行即可

### 页面特性
- 手机端卡片式布局，纯上下滑动，零横向滚动
- 卡片左侧彩色 accent 条：condo 金色 / landed 绿色 / room 蓝色，一眼区分类型
- 租金琥珀色 pill 标签，今日新房源绿色 NEW 徽章
- 详情彩色 chips（房型紫色、装修绿色），比纯文字更清晰
- 标签换行排列，不横滑
- 关键词搜索（楼盘名/agent/房型/备注）
- agent 行圆形头像 + 号码点击拨打
- 帖子原文展开/收起（超过 80 字折叠）
- 骨架屏加载动画，毛玻璃吸顶 header
- 深色主题，与 architecture.html 风格一致
- 数据驱动：空字段不显示，简洁无冗余

---

## Cron 调度（全链路自动化）

> **2026-05-16 优化：** 除隧道同步外，13个任务已切为 `no_agent=true`（纯脚本模式，零LLM费用）。崩了自动发告警，不再每趟调大模型。Form自动检查已删除（用户改用Google登录）。

| 时间 | 命令 | 工作目录 | 职责 |
|------|------|----------|------|
| 每 5 分钟 | `auto_sync_tunnel.sh` | `/home/user/jb-rental-intel` | 🔐 检测 Cloudflare Tunnel URL 变化 → 自动同步 `rentals.html` + commit + push |
| 每 30 分钟 | `node scraper/fb_scraper.js` | `/home/user/jb-rental-intel` | ① 采集 FB 帖子（6 群组） |
| 每天 10:29 | `python3 outreach/lib/maintain_agents.py` | `/home/user/jb-rental-intel` | ③ 更新 Agent List（去重） |
| 每天 10:30 | `python3 outreach/outreach_engine.py --send --slot 1 --total-slots 5` | `/home/user/jb-rental-intel` | ③ 推广时段①（1人） |
| 每天 11:30 | `python3 outreach/outreach_engine.py --send --slot 2 --total-slots 5` | `/home/user/jb-rental-intel` | ③ 推广时段②（1人） |
| 每天 12:30 | `python3 outreach/outreach_engine.py --send --slot 3 --total-slots 5` | `/home/user/jb-rental-intel` | ③ 推广时段③（1人） |
| 每天 13:30 | `python3 outreach/outreach_engine.py --send --slot 4 --total-slots 5` | `/home/user/jb-rental-intel` | ③ 推广时段④（1人） |
| 每天 14:30 | `python3 outreach/outreach_engine.py --send --slot 5 --total-slots 5` | `/home/user/jb-rental-intel` | ③ 推广时段⑤（1人） |
| 每 30 分钟 | 导出房源 JSON → git push | `/home/user/jb-rental-intel` | 📋 房源浏览页数据刷新（唯一入口，已去重） |
| 每 5 分钟 | `python3 sub_mgr.py form-process` | `/home/user/jb-rental-intel` | ④ 新注册 → 自动开试用 |
| 每天 9:00 | `python3 sub_mgr.py remind` | `/home/user/jb-rental-intel` | ④ 试用到期提醒 |
| 每天 0:00 | `python3 sub_mgr.py check` | `/home/user/jb-rental-intel` | ④ 到期回收权限 |
| 每 30 分钟 | `python3 sub_mgr.py stripe-check` | `/home/user/jb-rental-intel` | ⑤ Stripe 付款 → 自动续费 |
| **每天 9:00** | `python3 outreach/notify_subscribers.py morning` | `/home/user/jb-rental-intel` | 订阅早报推送 |
| **每天 13:00** | `python3 outreach/notify_subscribers.py afternoon` | `/home/user/jb-rental-intel` | 订阅午间推送 |
| **每天 18:00** | `python3 outreach/notify_subscribers.py evening` | `/home/user/jb-rental-intel` | 订阅日报推送 |

---

## Facebook Cookies 管理

### 获取 Cookie

1. Chrome 打开 facebook.com（已登录）
2. F12 → Application → Cookies → facebook.com
3. 复制以下字段：
   - `c_user` — 用户 ID
   - `xs` — 会话 token
   - `fr` — 浏览器指纹
   - `presence` — 在线状态

### 更新 Cookie

编辑 `scraper/fb_scraper.js` 第 21-26 行的 `COOKIES` 数组。

### Cookie 过期症状

- 输出 0 条帖子
- 出现 "browser has been closed"
- 需要重新登录的页面

---

## Google Sheets & Forms

### 服务账号认证（永不过期）

使用 Google Service Account 代替用户 OAuth，无需浏览器授权。

| 项目 | 值 |
|------|-----|
| SA Key 文件 | `/home/user/.hermes/google_sa_rental.json` |
| SA 邮箱 | `hermes-agent@gen-lang-client-0782646772.iam.gserviceaccount.com` |
| 权限范围 | Spreadsheets + Drive + Forms |

> ⚠️ 新 Sheet 需要手动共享给 SA 邮箱（编辑者权限）。SA 自己创建的 Sheet 自动归它所有。

### 关键 ID

| 资源 | ID |
|------|-----|
| JB Rentals Sheet（客户可见） | `1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM` |
| 内部运营 Sheet（不共享给客户） | `1gCynpcBHYgoGiRkfVOJOCOjtiOIl0NuGgpyEexAF3W4` |
| Google Form | `1oZTQNl3PF8TOu7RsG2SZeGjx5goT-o2Jy0TL7RlBiIQ` |
| Form Response Sheet | `1zLOyuRbZnycvD0tc4UPLSoR3mfClwkiDOPw3W-v-gXg` |

### 备份所有 Sheets（操作前必做！）

```bash
GAPI="python3.12 ~/.hermes/skills/productivity/google-workspace/scripts/google_api.py"
BACKUP=~/google_sheets_backup/$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP

$GAPI drive download 1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM --output $BACKUP/JB_Rentals.csv
$GAPI drive download 1zLOyuRbZnycvD0tc4UPLSoR3mfClwkiDOPw3W-v-gXg --output $BACKUP/Form_Responses.csv
```

### 认证检查

```bash
cd /home/user/jb-rental-intel
python3 -c "
from processors.fb_parser import get_sheets_service
svc = get_sheets_service()
r = svc.spreadsheets().get(spreadsheetId='1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM').execute()
print('✅ SA 认证正常:', r.get('properties',{}).get('title','?'))
"
```

---

## sub_mgr.py 常用命令

```bash
cd /home/user/jb-rental-intel

# 查所有订阅者
python3 sub_mgr.py list

# 查某人状态
python3 sub_mgr.py status <email>

# 手动开试用
python3 sub_mgr.py trial <email> <name> standard <phone>

# 手动续费
python3 sub_mgr.py renew <email> --days 30

# 检查到期（回收权限 + WhatsApp 通知）
python3 sub_mgr.py check

# 提醒试用到期
python3 sub_mgr.py remind

# Stripe 付款检测 → 自动续费
python3 sub_mgr.py stripe-check
```

---

## WhatsApp 维护

```bash
# 检查 Daemon 是否在线
curl -s http://localhost:3456/health

# 手动发消息
node wa/wa_notify.js send 60123456789 "测试消息"

# 查看 Daemon 日志
tail -f .logs/wa_daemon.log

# 重新扫码登录（如果掉线）
# 删除 wa_session/ 重新启动 daemon
```

---

## 数据清洗工具

### 电话号格式化

```bash
cd /home/user/jb-rental-intel

# 干跑（预览变更）
python3 scripts/clean_phones.py

# 写入 Sheet
python3 scripts/clean_phones.py --apply
```

一次性清洗（2026-05-14）：471 → +60 国际格式，6 格无效号清空。
Parser 已集成 `normalize_phone()`，新数据自动标准。

### 楼盘名标准化

```bash
cd /home/user/jb-rental-intel

# 干跑
python3 scripts/clean_property_names.py

# 写入 Sheet
python3 scripts/clean_property_names.py --apply
```

一次性清洗（2026-05-14）：391 → 218 独特值，301 行无楼盘名清空。
Parser 已集成 `normalize_property_name()` + `_is_valid_property_name()`，新数据自动标准。

---

## 故障排查

| 症状 | 可能原因 | 解决 |
|------|----------|------|
| 爬虫 0 条帖子 | FB Cookie 过期 | 重新获取 Cookie |
| `browser has been closed` | FB 反爬检测 | 增加 `waitForTimeout` 间隔 |
| WhatsApp 发不出去 | Daemon 掉线 | 重启 `node wa/wa_daemon.js` |
| `RefreshError: invalid_scope` | SA Key 没共享给目标 Sheet | 在 Sheet 中共享给 SA 邮箱（编辑者） |
| Stripe 检测不到付款 | Token 过期 | 检查 `.env` 中 `STRIPE_SECRET_KEY` |
| `googleapiclient` 找不到 | 用错 Python | 使用 Hermes Agent venv 的 `python3` |
| `[remote rejected] cannot lock ref` | 多个 cron 同时 git push 冲突 | 只保留 1 个导出 cron，删掉重复的（2026-05-14 已修复） |
| Post Text 全是 FB 界面噪音 | 旧版 clean_post_text 不够强 | 已重写，新帖自动干净；旧数据跑 `python3 /tmp/clean_batch.py` |
| Agent 名是随机英文（ThrillingGrapefruit） | FB 给匿名用户生成的显示名 | fb_extract.js 自动检测并替换为真实姓名；已有数据跑清理脚本 |
| Rent 列为空但帖文有价格 | ① 价格被清洗函数吃掉 ② MYR 不被识别 | 已修：提取前先读 raw text + 支持 MYR；回填脚本见 /tmp/backfill_v2.py |
| Phone 列格式混乱 | ① 旧数据未清洗 ② 新帖 Parser 未规范化 | ① `python3 scripts/clean_phones.py` ② Parser 已集成（2026-05-14） |
| Sheet 美化后想还原 | 格式太花/不合口味 | `python3 scripts/reset_sheet_format.py` 一键清回裸数据 |
| rentals.html 登录报错 | auth_server 或 Cloudflare Tunnel 挂了 | `bash auth/start_auth.sh` 重启，检查 `curl .../health`；隧道 URL 变化由 `auto_sync_tunnel.sh` 自动同步，无需手动更新 |
| 隧道 URL 变了但 rentals.html 仍指向旧地址 | auto_sync 脚本未运行或失败 | 检查 cron `f508f32bed96` 状态；手动执行 `bash /home/user/jb-rental-intel/scripts/auto_sync_tunnel.sh` |

---

## 辅助脚本速查

| 脚本 | 路径 | 用途 |
|------|------|------|
| Sheet 美化 | `scripts/beautify_sheet.py` | 格式化 Sheet（冻结、斑马纹、条件颜色、列宽） |
| Sheet 还原 | `scripts/reset_sheet_format.py` | 清除所有格式，回到裸数据 |
| 电话号清洗 | `scripts/clean_phones.py` | 一次性清洗 Phone 列 → +60 国际格式 |
| 楼盘名清洗 | `scripts/clean_property_names.py` | 一次性标准化 Property Name + 去垃圾 |
| 租金回填 | `/tmp/backfill_v2.py` | 从 raw JSON 补填空租金（一次性的） |
| Agent 名清理 | `/tmp/clean_agent_only.py` | 清掉FB随机用户名（一次性的） |
| 🔐 Auth 服务 | `auth/start_auth.sh` | 启动 auth_server + Cloudflare Tunnel（@reboot cron） |
| 🔐 隧道同步 | `scripts/auto_sync_tunnel.sh` | 每5分钟检测 Tunnel URL 变化 → 自动更新 `rentals.html` + push（cron 静默） |
| 🔐 手动登录测试 | 打开 `https://reinocheong.github.io/jb-rental-intel/rentals.html` | 测试用户: test@example.com / test123 |