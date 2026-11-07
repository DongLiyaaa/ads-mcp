# ads-cli

Amazon Ads 的命令行工具和 MCP 控制台，供 AI 广告员工或人工运营调用。

- **CLI**：覆盖 Sponsored Products / Sponsored Brands / Sponsored Display 的查询、报表和写操作，输出结构化 JSON，方便 Agent 解析。
- **MCP 控制台（可选）**：在 CLI 之上加了 PostgreSQL 持久化、后台报表任务、Streamable HTTP MCP 和中文管理页面。模型只能提交计划，**必须由用户确认后才会真正修改广告**：在页面上确认，或给 Token 开启“在对话中确认执行变更”权限后，用户在对话里回复“确认”。

> 本仓库不包含任何凭证、账户标识或报表数据。

## 两种用法怎么选

| 用法 | 适合场景 | 优势 | 劣势 |
| --- | --- | --- | --- |
| 只用 CLI | 本机脚本、Codex / Claude 等本地 Agent 直接调命令 | 安装简单，不需要数据库和容器；命令即契约，`--json` 输出稳定 | 凭证在本机环境变量里；任务和结果不持久化；审批靠对话里回复“确认” |
| MCP 控制台 | 多个广告账户、远程 MCP 客户端、需要留痕和人工审批 | 凭证加密入库；每个 Token 限定账户和权限；报表后台执行并分页入库；审批和执行日志可追溯 | 需要 Docker + PostgreSQL；首次部署要做容器影响评估；客户端要支持自定义 `Authorization` 请求头 |

## 能力概览

| 范围 | 内容 |
| --- | --- |
| Sponsored Products | Portfolio、广告活动、广告组、关键词、商品广告、商品/类目定向、否定关键词、否定商品定向，以及预算、竞价策略、广告位溢价 |
| Sponsored Brands | 广告活动、广告组、关键词、定向、否定关键词、否定定向（不含创意/素材上传） |
| Sponsored Display | 广告活动、广告组、商品广告、定向、受众、地域、预算规则、快照 |
| 报表 | SP 广告活动、广告组、广告位、投放、关键词、搜索词、搜索顶部展示份额、推广的商品、已购买的商品、总流量和无效流量；SB 活动、广告组、定向、搜索词、广告位；SD 活动、广告组、商品广告、定向，共 19 类；支持下载和本地解析 |
| AMC（Amazon Marketing Cloud） | 自动识别账户的 AMC 实例；6 个内置分析模板（广告类型组合、转化时长、品牌新客、曝光频次、搜索词、分时段）和自定义 SQL；结果进入数据表格，MCP 同样可用 |
| 代理转发 | 每个店铺可选本地直连或经自己的服务器转发（Amazon 请求从服务器发出，数据回传本机）；控制台通过 SSH 检测服务器并一键安装 systemd 转发服务，TLS 证书指纹固定 + 请求签名，只转发 Amazon 地址 |
| Agent 契约 | `capabilities` 输出机器可读的操作清单；控制台对外提供 142 个操作契约（36 个查询、85 个写操作、21 个报表） |

“已封装”不等于“已在真实账户实测”。实测范围以 [验证记录](VERIFICATION.md) 为准。

## 安全模型

- **写操作默认不直接提交。** CLI 写命令先生成审批计划（带 `planId` 和请求摘要），用户回复 `确认` 后才执行 `approvals execute`；`--dry-run` 只预览请求体。
- **控制台里写操作必须经用户确认。** 默认由人登录页面、核对精确请求并输入“确认”。Token 开启可选权限 `changes:approve` 后，用户在对话里回复“确认”，AI 可调用 `ads_confirm_change` 直接执行——仅限该 Token 自己提交的计划，确认文本必须是“确认”，并校验请求摘要。审批绑定用户、账户、Profile、操作和请求内容，24 小时过期。
- **凭证分开管理。** Amazon OAuth 凭证用 Fernet 加密保存；MCP Token 以摘要校验，明文另用 Fernet 加密保存，管理员可在页面一键复制或查看（撤销或删除时清除；旧版本生成的 Token 可“重新生成”新值后复制）；会话令牌只存摘要；管理密码用 scrypt。MCP Token 和 Amazon 凭证是两套认证，不能互换。
- **结果不确定时不自动重发。** 写操作中断标记 `UNKNOWN`，需要先查询远端核实。
- **转发不回落。** 店铺绑定的转发服务器不可用时直接报错，不会改走本机直连；SSH 私钥/密码加密保存、从不回显。
- **限制并发。** 对 Amazon 的并发调用默认 3、最多 5。

## 快速开始：CLI

需要 Python 3.10+。

```bash
cd agent-harness
python -m pip install -e .
```

在本机环境里设置 Amazon Ads 凭证（变量名见 `.env.example`，真实值不要提交到 Git）：

```bash
export AMAZON_ADS_CLIENT_ID=...
export AMAZON_ADS_CLIENT_SECRET=...
export AMAZON_ADS_REFRESH_TOKEN=...
export AMAZON_ADS_PROFILE_ID=
export AMAZON_ADS_REGION=NA
export AMAZON_ADS_MARKETPLACE=US
```

常用命令：

```bash
ads=cli-anything-amazon-ads-ops-workbench

# 查询
$ads --json auth health
$ads --json campaigns list --marketplace US
$ads --json keywords list --campaign-id 123
$ads --json negatives list --campaign-id 123 --scope both
$ads --json snapshot --marketplace US

# 报表
$ads --json reports create-sp-keywords --start-date 2026-07-01 --end-date 2026-07-07
$ads --json reports create-search-terms --start-date 2026-07-01 --end-date 2026-07-07
$ads --json reports create-sp-campaign-placement --start-date 2026-07-01 --end-date 2026-07-07 --time-unit DAILY

# 写操作：先预览，再生成审批计划，用户确认后执行
$ads --json keywords edit-bid --campaign-id 123 --ad-group-id 456 --keyword-id 789 --bid 0.92 --dry-run
$ads --json keywords edit-bid --campaign-id 123 --ad-group-id 456 --keyword-id 789 --bid 0.92
$ads --json approvals show --plan-id <PLAN_ID>
$ads --json approvals execute --plan-id <PLAN_ID> --confirm-text 确认
```

完整命令和 SP/SB/SD 对照表见 [CLI 说明](agent-harness/cli_anything/amazon_ads_ops_workbench/README.md)。

## 快速开始：MCP 控制台

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-server.lock
.venv/bin/python -m pip install --no-deps -e ./agent-harness
.venv/bin/ads-control init-env      # 生成 .env（0600，数据库密码与加密密钥），已存在时不会覆盖
(cd web && npm ci && npm run build)

.venv/bin/python deploy/preflight.py
docker compose config --quiet
docker compose build api
docker compose up -d postgres api
docker compose up -d worker
```

> 启动前请先阅读 [容器影响清单](deploy/IMPACT.md)，确认不会影响本机已有容器。三个容器（api / worker / postgres）均为 `linux/amd64`，使用独立网络和数据卷，数据库端口不对宿主机开放。

| 入口 | 地址 |
| --- | --- |
| 管理页面 | `http://127.0.0.1:16666`（Chromium 禁止网页访问 6666 端口，所以另开 16666） |
| MCP（Streamable HTTP） | `http://127.0.0.1:16666/mcp/`；非浏览器客户端也可用 `http://127.0.0.1:6666/mcp/` |
| 管理账号 | 首次打开页面时自己创建（只能创建一次）；登录后可在侧栏修改密码，忘记密码可在登录页一键重置。远程部署需在 `.env` 设置 `ADS_SETUP_TOKEN`，创建和重置时都要填写 |

默认只绑定 `127.0.0.1`。如需远程访问，请放在 HTTPS 反向代理之后，并设置 `ADS_PUBLIC_ORIGIN` 和 `ADS_SECURE_COOKIES=true`。

### 接入 MCP 客户端

登录管理页面并连接广告账户，然后到“MCP Token”页生成令牌（之后可随时在列表里再次复制）：

```text
URL: http://127.0.0.1:16666/mcp/
Authorization: Bearer <页面生成的 Token>
```

| 工具 | 用途 |
| --- | --- |
| `ads_accounts` | 列出该 Token 可访问的账户 |
| `ads_capabilities` | 获取操作列表和参数 Schema |
| `ads_query` | 创建查询任务 |
| `ads_create_report` | 创建后台报表任务 |
| `ads_plan_change` | 生成待用户确认的变更计划 |
| `ads_confirm_change` | 用户在对话里回复“确认”后提交执行（需 `changes:approve` 权限） |
| `ads_task_status` | 查看任务状态和结果摘要 |
| `ads_task_rows` | 分页读取已入库的数据 |
| `ads_tasks` | 列出可访问的任务 |

页面、任务状态、数据限制和部署细节见 [控制台说明](CONTROL_PLANE.md)。

## 目录结构

```text
agent-harness/   Python 包：CLI、核心 API 封装、控制台服务（control_plane/）和测试
web/             控制台前端（React 19 + TypeScript + Vite）
deploy/          容器影响清单、预检脚本、数据库初始化 SQL、验收脚本
skills/          Agent 路由用的 Skill 入口
docs/            接口缺口与后续扩展设计
compose.yaml     api / worker / postgres 三容器编排
```

## 开发与测试

```bash
.venv/bin/python -m pytest \
  agent-harness/cli_anything/amazon_ads_ops_workbench/tests/test_core.py \
  agent-harness/cli_anything/amazon_ads_ops_workbench/tests/test_full_e2e.py \
  agent-harness/cli_anything/amazon_ads_ops_workbench/control_plane/tests/test_contracts.py \
  agent-harness/cli_anything/amazon_ads_ops_workbench/control_plane/tests/test_http_mcp.py -q
```

PostgreSQL 集成测试只能在空库上运行，用法见 [控制台说明](CONTROL_PLANE.md)。测试计划见 [CONTROL_PLANE_TEST_PLAN.md](CONTROL_PLANE_TEST_PLAN.md)，最新结果见 [VERIFICATION.md](VERIFICATION.md)。

## 当前边界

- 单管理工作空间，可管理多个广告账户；不是带注册、计费、组织管理的 SaaS。
- MCP 使用自有 Bearer Token，不支持客户端 OAuth 动态注册。
- SB/SBV 的创意、图片、视频、Logo、落地页等素材上传不支持。
- 单个报表最多 31 天，下载上限 64 MiB / 25 万行，大报表需要拆分日期。
- 取消任务只停止本地排队，不会取消 Amazon 端已开始生成的报告。

## 隐私

- 不要提交 `.env`、Refresh Token 或生成的报表文件。
- 公开文档里不要出现真实的活动、Profile、报表标识。
- `.env.example` 只写变量名，不写真实值。

## 作者

- GitHub：[DongLiyaaa](https://github.com/DongLiyaaa)
- 微信公众号：冬离鸭冬离
- 抖音号：冬离鸭冬离

## 许可证

[MIT](LICENSE)
