# ARCHITECTURE.md — Smart Tenancy Pro 全景架构

## 🗺️ 系统拓扑图

```mermaid
graph TD
    %% 外部数据源
    FB[(Facebook Groups)] -- "① 采集" --> Scraper[scraper/fb_scraper.js]
    
    %% 第一阶段：采集
    subgraph Stage1 [Phase 1: Scraping]
        Scraper -->|提取文本/号码| RawJSON[(fb_posts_raw.json)]
    end
    
    %% 第二阶段：解析
    subgraph Stage2 [Phase 2: Processing]
        RawJSON -- "② 解析" --> Parser[processors/fb_parser.py]
        Parser -->|结构化字段| Sheets[(Google Sheets: JB Rentals)]
    end
    
    %% 第三阶段：推广
    subgraph Stage3 [Phase 3: Outreach]
        Sheets -->|读取 Agent| Maintainer[outreach/lib/maintain_agents.py]
        Maintainer --> AgentList[(Agent List)]
        AgentList -- "③ 推广" --> Engine[outreach/outreach_engine.py]
        Engine -->|调用| WADaemon[wa/wa_daemon.js]
        WADaemon -->|发送| WA((WhatsApp))
    end
    
    %% 第四五阶段：订阅与支付
    subgraph Stage45 [Phase 4 & 5: Subscription & Payment]
        User[Agent/User] -->|④ 登录/试用| AuthServer[auth/auth_server.py]
        AuthServer -->|读写| SubDB[(subscribers.db)]
        User -->|⑤ 付费| Stripe((Stripe Checkout))
        Stripe -->|通知| StripeChecker[stripe_checker.py]
        StripeChecker -->|更新状态| SubMgr[sub_mgr.py]
        SubMgr --> SubDB
    end

    %% 日志监控
    LogService[.logs/error.log]
    Scraper -.-> LogService
    Parser -.-> LogService
    Engine -.-> LogService
    AuthServer -.-> LogService
```

## 🌊 核心数据流

```mermaid
sequenceDiagram
    participant FB as FB 群组
    participant Scraper as 爬虫 (Node.js)
    participant Parser as 解析器 (Python)
    participant Sheets as Google Sheets
    participant Engine as 推广引擎
    participant User as 最终用户

    FB->>Scraper: 滚动抓取帖子文本
    Scraper->>Scraper: 提取电话 (Regex)
    Scraper->>Parser: 写入原始 JSON
    Parser->>Parser: 清洗噪音/识别楼盘
    Parser->>Sheets: 更新 JB Rentals 表
    Sheets->>Engine: 读取最新 Agent
    Engine->>User: 发送 WhatsApp 邀请
    User->>User: 登录 rentals.html
```

## 🧩 模块依赖与状态边界

- **Global Context (全局状态):** 
    - `subscribers.db`: 订阅者生命周期。
    - `Google Sheets`: 房源与推广记录的 SSOT。
    - `.env`: 敏感凭据 (Stripe/Google Key)。
- **Local State (局部状态):**
    - `wa_session/`: WhatsApp 认证会话。
    - `fb_posts_raw.json`: 采集阶段的中间缓存。
    - `.form_processed.json`: 注册表单处理位点。

## 🚨 日志与异常边界

- 所有的核心服务 (Auth, Scraper, Parser, outreach) 必须捕获异常并写入 `.logs/error.log`。
- 调用深度严禁超过 4 层（例如：Engine -> Sender -> Notify -> Daemon ✅）。
