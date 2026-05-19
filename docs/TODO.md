# TODO.md — 进度表

> 项目：Smart Tenancy Pro — JB 房产数据 SaaS  
> 根目录：`/home/user/jb-rental-intel/`  
> 最后更新：2026-05-19

---

## 🎯 规范化整改进度 (AI_ARCHITECT_PROTOCOL)

| 阶段 | 描述 | 状态 | 备注 |
|:----|:----|:----:|:----|
| **0** | Git 版本基线 | ✅ | Tag: `pre-refactor-v1` |
| **1** | SSOT 文档补齐 | [-] | USER/JOURNAL/MEMORY 已建，TODO 更新中 |
| **2** | Mermaid 架构图 | [ ] | 待重写 ARCHITECTURE.md |
| **3** | 核心模块化拆分 | [ ] | 涉及 fb_parser, sub_mgr 等 |
| **4** | 日志系统标准化 | [ ] | 待建 error.log 与统一格式 |
| **5** | 最终审计校验 | [ ] | 待完成 |

---

## 🚀 业务模块进度

| 阶段 | 模块 | 状态 | 关键文件 |
|------|------|:----:|------|
| ① 数据采集 | FB 爬虫 | ✅ | `scraper/fb_scraper.js` |
| ② 数据解析 | 结构化 → Sheets | ✅ | `processors/fb_parser.py` |
| ③ 推广触达 | WhatsApp 推广 | ✅ | `outreach/outreach_engine.py` |
| ④ 试用管理 | 登录/试用/回收 | ✅ | `sub_mgr.py` + `auth/auth_server.py` |
| ⑤ 付费续费 | Stripe 自动续费 | ✅ | `stripe_checker.py` |

---

## 📝 待办事项清单

### 🔴 高优先级 (近期执行)
- [ ] **Mermaid 架构可视化：** 在 `docs/ARCHITECTURE.md` 中绘制全景图。
- [ ] **日志系统升级：** 实现 `.logs/error.log` 并审计所有 catch 块。
- [ ] **超大文件拆分：**
    - `fb_parser.py` (1065行) 拆分为字段提取、Sheet 写入等模块。
    - `sub_mgr.py` (754行) 拆分为 DB、命令处理、通知等模块。

### 🟡 中优先级 (稳定性)
- [ ] **`wa_listener.js` 闭环：** 完善 agent 回复识别逻辑，自动更新推广记录状态。
- [ ] **Cookie 过期告警：** 爬虫检测到登录失败时发送 WhatsApp/Telegram 告警。

### 🟢 低优先级 (长期维护)
- [ ] **前端代码分离：** 将 `rentals.html` 中的 CSS/JS 抽离到独立文件。
- [ ] **清理冗余脚本：** 审计并移除 `archived/` 和 `scripts/` 中的过期工具。
