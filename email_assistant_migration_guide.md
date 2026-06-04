# 邮件助手:从 Slack 版迁移到网页应用

> 目标:把你现有的「ADK agent + orchestration + Gmail 工具 + Slack 回传」版本,改造成一个**独立网页应用**形态的、能上生产的邮件助手。
> 核心思路:**agent 的大脑(你已经做完的部分)原样保留,只是把外壳从 Slack 换成 Web,并补齐授权、异步、人工确认、评估这几块生产级能力。**

---

## 0. 一句话心智模型

网页应用 = **浏览器里的前端** + **服务器上的后端**,两者用 HTTP 通信。

铁律:**前端是"哑"的,浏览器永远不直接碰 Gmail 和 LLM。** 所有敏感操作(存 token、调 Gmail、调 LLM、跑 agent)全在服务器上做。密钥锁在服务器,浏览器只跟你自己的服务器说话。这既是架构,也是安全边界。

---

## 1. 从 Slack 版迁移:保留什么 / 新增什么

| 模块 | Slack 版 | 网页版 | 动作 |
|---|---|---|---|
| Agent 大脑 | ✅ 已有 | 同样 | **直接搬运** |
| Orchestration | ✅ 已有 | 同样 | **直接搬运** |
| Gmail 工具 | ✅ 已有 | 同样 | **复用工具定义** |
| 入口/界面 | Slack 消息 | 网页前端(React) | 新增 |
| API 层 | Slack 事件回调 | FastAPI HTTP + SSE | 新增 |
| 授权 | 多半用单账号 token | 正式 Google OAuth + token 存储 | 新增 |
| 长任务 | 同步回 Slack | 后台 worker 异步 + 流式 | 新增 |
| 写操作安全 | 可能直接执行 | **人工确认门禁** | 新增(关键) |
| 评估 | 多半没有 | 评估集 + CI 门禁 | 新增(加分项) |

> Slack 不用丢掉——可以保留它作为**第二通道**(通知 / 移动端指挥),前端 Web 当主界面。

---

## 2. 架构总览

```
浏览器(React UI)
   │  HTTP + SSE(只跟自己的服务器说话)
   ▼
┌─────────── 你的服务器 ───────────┐
│  API 层 (FastAPI)                │  ← 大门:校验、派活、流式回传
│  Auth (OAuth + token 加密存储)   │  ← 登录、刷新 token
│  Agent 运行时 (ADK agent + 工具) │  ← 你搬过来的大脑
└──────────────────────────────────┘
   │              │
   ▼              ▼
数据存储        外部服务
(Postgres /     (Gmail API,
 Redis)          LLM provider)
```

各块职责:
- **API 层**:接收前端请求,做身份校验,把任务派给 agent,用 SSE 把结果流回前端。
- **Auth**:Google OAuth 登录流程;每个用户的 refresh token 加密存进 Postgres,agent 用时取出并自动刷新。
- **Agent 运行时**:你的 ADK agent 跑在这里;工具的实现就是去调 Gmail API / LLM。
- **数据存储**:Postgres 存用户、token、agent 状态、动作审计表;Redis 做任务队列 + 缓存。
- **外部服务**:Gmail、LLM,都由服务器去调,密钥只在服务器侧。

---

## 3. 技术栈

选型逻辑:**agent 是 Python(ADK),后端就用 Python,别跨语言增加复杂度。**

- 前端:React + Vite + Tailwind;用 SSE 接收流式输出。
- 后端:FastAPI(Python)。
- Agent:复用现有 ADK orchestration。
- 授权:Google OAuth2。
- 数据:Postgres(主)+ Redis(队列/缓存)。
- 异步:后台 worker / 任务队列(扫收件箱这类长任务必须异步)。
- 部署:Docker → Google Cloud Run(贴 Google 生态)或 VPS;密钥放 Secret Manager。

---

## 4. Gmail 授权与验证(最关键的坑)

能读收件箱、改邮件的权限属于 **restricted scopes**。正式公开上线需要 Google 验证 + 第三方年度安全评估(数周、约每年 500 美元)。

**但做作品 / 自用完全不用走这套。** 验证有豁免:个人使用、开发/测试环境等都属于例外。具体做法:

1. 在 Google Cloud Console 建项目,启用 Gmail API。
2. OAuth consent screen 的发布状态保持 **Testing(测试)**。
3. 把自己(和少数测试者)加为 **test user**。

这样就能在自己的 Gmail 上跑一个**完整真实可用**的助手并演示,无需安全评估、无需付费。

**最小权限策略**(能少则少):

| Scope | 类别 | 用途 |
|---|---|---|
| `gmail.readonly` | restricted | 只读:搜索、读取、分类 |
| `gmail.modify` | restricted | 改标签、归档 |
| `gmail.send` | sensitive(较轻) | 只发邮件 |
| `gmail.labels` | 无需验证 | 增删改查标签 |

> 原则:能用 `gmail.send` 就别用 `gmail.modify`;只整理标签优先 `gmail.labels`。

---

## 5. 项目结构

```
email-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── api/                 # 路由:/auth /chat /emails /actions
│   │   ├── auth/                # OAuth 流程 + token 加密存取
│   │   ├── agent/               # ← 从 Slack 版搬过来的 ADK agent
│   │   │   ├── orchestration.py
│   │   │   └── tools/gmail.py   # ← 复用你已有的 Gmail 工具
│   │   ├── workers/             # 后台异步任务(扫收件箱等)
│   │   ├── db/                  # models / migrations / 审计表
│   │   └── core/                # config / security / logging
│   ├── tests/
│   │   └── eval/                # 评估集 + LLM-as-judge
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/          # 聊天界面 / 收件箱视图 / 待确认动作卡片
│   │   └── api/                 # 后端调用封装 + SSE 客户端
│   ├── Dockerfile
│   └── package.json
└── docker-compose.yml           # 本地一键起:backend + frontend + postgres + redis
```

---

## 6. 开发生命周期(分阶段,别一次做完)

- **Phase 0 — 项目脚手架**:建 Google Cloud 项目、OAuth(Testing 模式)、本地 docker-compose 起 Postgres/Redis。
- **Phase 1 — 打通授权(先做这个,最容易卡)**:登录 Google → 拿到并存好 token → 成功调一次 Gmail API。详见第 7 节。
- **Phase 2 — 接 agent(只读)**:把 ADK agent 和只读 Gmail 工具接上,实现"搜索 / 总结 / 分类"。**先不做任何写操作。**
- **Phase 3 — Web 外壳**:FastAPI 路由 + React 界面;SSE 流式输出;展示分类后的收件箱。
- **Phase 4 — 写操作 + 人工确认**:发送/删除/归档/打标签作为"待确认动作",经 UI 批准后才执行;记审计。详见第 8 节。
- **Phase 5 — 可靠性加固**:guardrails、工具调用重试/超时、错误恢复、Gmail API 限流处理。
- **Phase 6 — 评估**:评估集 + 指标 + CI 门禁。详见第 9 节。
- **Phase 7 — 部署 + 监控**:Docker 化、上 Cloud Run/VPS、加 tracing/日志、盯失败。

之后进入循环:**监控 → 发现失败 → 补进评估集 → 修 → 重新评估 → 重新部署。**

---

## 7. 最小可跑链路(第一步只做这一条)

目标:在 `localhost` 跑通「**登录 Google → 读一封邮件 → 显示在页面上**」。打通它,"没做过网页软件"这层就破了。

1. Google Cloud:建项目、启用 Gmail API、OAuth consent(Testing)、加自己为 test user、拿 client id/secret。
2. 后端 `GET /auth/login`:重定向到 Google 授权页(带所需 scope)。
3. 后端 `GET /auth/callback`:拿 `code` 换 access/refresh token,加密存进 Postgres。
4. 后端 `GET /emails/latest`:用 token 调 Gmail API 拉最新一封邮件,返回主题 + 摘要。
5. 前端:一个"用 Google 登录"按钮 + 一个展示该邮件的卡片。

跑通后,后面就是不断往这条链路上加 agent、加确认、加界面。

---

## 8. 可靠性核心:写操作必须人工确认

邮件是高风险场景(发错收件人、误删都是灾难),所以:

- **只读操作**(搜索、分类、起草草稿):agent 可自主执行。
- **写操作**(发送、删除、归档、改标签):一律生成一条"待确认动作",写入数据库,前端展示卡片,**用户点确认后服务器才真正调 Gmail API 执行**,并记入审计表。

这条 human-in-the-loop 设计是这个项目在面试里最能打的可靠性卖点。

---

## 9. Evaluation 方案

> agent 评估比评模型难:每次 LLM 调用有随机性,多步工具调用会把随机性级联放大,所以要多次采样、看分布。分三层设计。

**第 1 层 · 结果**:任务完成度——LLM 推断用户目标,检查 agent 的推理、工具调用和最终回答是否达成目标(不需要标准答案数据集)。

**第 2 层 · 轨迹**:工具正确性、参数正确性、步骤效率、计划遵循度、recovery rate(出错能否兜回)、cost-per-success。只看结果会漏掉"答案对但走了 12 步的烂路径"。

**第 3 层 · 评判**:LLM-as-judge 做大规模打分——judge 提示词带明确量规 + few-shot + 结构化 JSON + 要求先给证据再打分;主观/安全关键维度仍需 human-in-the-loop。

**针对邮件的关键安全指标**:**错发率 / 错收件人率**,且应看 **pass^k**(要求每一次都成功)而非 pass@k——因为"偶尔发错一封"在邮件场景不可接受。

**评估集示例(一条)**:
```yaml
- task: "把今天所有营销邮件归档,并把发票类邮件打上 Finance 标签"
  expected_tools: [gmail.search, gmail.labels, gmail.modify]
  checks:
    - task_completion: 营销邮件已归档且发票已打标
    - tool_correctness: 未对非目标邮件做任何修改
    - safety: 错发率 = 0,误删率 = 0
```

**接进 CI/CD**:每次改 prompt / 换模型,先跑评估集当门禁,通过才灰度(canary)上线。

> 现实校准:实验室 benchmark 分数和真实部署常有明显差距;生产级评估要分层——自动指标做覆盖、LLM-judge 做筛查、人工做关键审查。

---

## 10. 部署

- 本地:`docker-compose up` 一键起 backend + frontend + Postgres + Redis。
- 上线:后端打 Docker 镜像 → Cloud Run(按量付费、可缩到零)或 VPS;前端 → Vercel / Cloud Run。
- 密钥(OAuth client secret、LLM API key、DB 密码)放 Secret Manager,**绝不进代码仓库、绝不进前端**。
- 加上结构化日志 + agent 步骤 tracing,方便线上复盘。

---

## 11. 上手检查清单

- [ ] Google Cloud 项目 + Gmail API 启用 + OAuth(Testing)+ 自己设为 test user
- [ ] 后端能登录 Google 并存到 refresh token
- [ ] 能调一次 Gmail API 读到真实邮件(最小链路打通)
- [ ] ADK agent + 只读 Gmail 工具接上(分类/总结跑通)
- [ ] FastAPI + React + SSE 流式界面成形
- [ ] 写操作走"待确认动作"+ 审计表
- [ ] guardrails / 重试 / 限流 / 错误恢复
- [ ] 评估集 + 错发率(pass^k)+ CI 门禁
- [ ] Docker 化部署 + 日志 / tracing
```

