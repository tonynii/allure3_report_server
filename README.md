# Allure3 Report Service

基于 FastAPI 的全托管 Allure 3 测试报告平台。用户通过 API 或 Web 界面上传 pytest `allure-results`，平台自动生成 Allure 3 静态 HTML 报告，支持按项目划分、历史追踪、附件下载、多 Run 横向对比。测试结果结构化存入 PostgreSQL 供 LLM 分析。

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 22+ (Allure 3 CLI)
- Docker & Docker Compose (推荐)
- PostgreSQL 16 (Docker Compose 已包含)

### Docker Compose 一键部署

```bash
git clone https://github.com/tonynii/allure3_report_server.git
cd allure3_report_server
docker compose up -d
```

启动后访问：

| 地址 | 内容 |
|------|------|
| `http://localhost` | Vue3 前端 Web 界面 |
| `http://localhost/docs` | Swagger API 文档 |
| `http://localhost/api/health` | 健康检查 |

### 本地开发

```bash
# ── 后端 ──
cd backend
uv sync                                    # 安装依赖
uv run alembic upgrade head                # 数据库迁移
uv run uvicorn app.main:app --reload       # 启动 API (localhost:8000)

# ── 前端 ──
cd frontend
npm install                                # 安装依赖
npm run dev                                # 启动前端 (localhost:5173)
```

## 使用流程

### Web 界面

1. 打开 `http://localhost`，看板主页展示项目概况
2. 通过「📁 项目」创建/管理项目，或「🔧 工具」上传报告
3. 项目详情：Stats 卡片 + 饼图/趋势图 + Run 历史表格
4. Run 详情：结构化测试列表（筛选/搜索）→ 点击测试查看步骤/错误/附件
5. 「📊 横向对比」支持多项目/多 Run 同时对比，发现回归和共同失败

### CLI 上传脚本

```bash
cd backend
uv run ../scripts/upload.py --project my-app ./allure-results/
uv run ../scripts/upload.py -s https://reports.example.com -p my-app -b main ./allure-results/
```

### curl 手动调用

```bash
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"key":"my-app","name":"My Application","max_runs":20}'

curl -X POST http://localhost:8000/api/projects/my-app/runs \
  -F "file=@allure-results.zip" -F "branch=main"
```

## 前端页面

### 侧边栏菜单

| 菜单 | 路由 | 说明 |
|------|------|------|
| 📊 看板 | `/` | Dashboard 主页：项目数/Runs/通过率 + 项目概况卡片 + 最近运行 |
| 📁 项目 | `/projects` | 项目卡片网格 + 创建/删除 |
| 🔧 工具 | `/tools` | 上传 allure-results.zip + 📊 横向对比入口 |
| ⚙️ 配置 | `/settings` | Allure 版本、数据目录、项目概况表（✏️编辑 🗑删除） |

### 全部页面

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | DashboardPage | 看板主页：统计卡片 + 项目概况 + 最近运行列表 |
| `/projects` | ProjectsPage | 项目卡片网格 + 创建/删除 |
| `/projects/:key` | ProjectDetail | Stats卡片 + 饼图/趋势图 + Run表格（📊📄🗑） |
| `/projects/:key/runs/:id` | RunDetail | 测试列表 + 状态筛选 + 搜索 + 🗑删除 |
| `/projects/:key/runs/:id/tests/:tid` | TestDetail | 步骤树 + 错误堆栈 + 附件下载 |
| `/projects/:key/reports/latest` | ReportViewer | iframe 嵌入最新 Allure HTML |
| `/projects/:key/reports/:id` | ReportViewer | iframe 嵌入历史 Allure HTML |
| `/tools` | ToolsPage | 选择项目上传 allure-results.zip |
| `/tools/compare` | ComparePage | 多 Run 横向对比矩阵 |
| `/settings` | SettingsPage | Allure 版本 + 数据目录 + 项目概况编辑 |

### 双入口设计

| 按钮 | 数据来源 | 行为 |
|------|----------|------|
| 📊 详情 | PostgreSQL 结构化数据 | `router.push` → RunDetail / TestDetail |
| 📄 报告 | Allure 静态 HTML | `window.open` 新标签 / iframe |

### 删除功能

| 位置 | 确认方式 |
|------|----------|
| 项目卡片 | `n-popconfirm` |
| Run 表格 | `dialog.warning()` 模态框 |
| RunDetail 头部 | `n-popconfirm` |
| 配置页项目表 | `dialog.warning()` 模态框 |

### 横向对比

多 Run 横向对比，入口：`🔧 工具` → `📊 横向对比`

- 支持同项目不同分支/历史 Run、跨项目对比
- 按 `historyId` 匹配同一测试在不同 Run 中的结果
- 分类：全部通过 / 全部失败 / 有差异 / 不稳定
- 支持关键词搜索 + "仅显示有变化" 过滤
- 点击行弹窗展示详情（错误信息、Labels）

### 奇偶行交替

所有数据表格均支持奇偶行交替灰白背景。

## API 端点

### 项目管理

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/projects` | 创建项目 |
| `GET` | `/api/projects` | 项目列表 |
| `GET` | `/api/projects/{key}` | 项目详情 |
| `PUT` | `/api/projects/{key}` | 更新项目 |
| `DELETE` | `/api/projects/{key}` | 删除项目及所有数据 |

### 报告管理

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/projects/{key}/runs` | 上传 allure-results.zip → 202 |
| `GET` | `/api/projects/{key}/runs` | 所有 runs 列表 |
| `GET` | `/api/projects/{key}/runs/{id}` | run 详情 + 测试统计 |
| `DELETE` | `/api/projects/{key}/runs/{id}` | 删除单个 run |
| `GET` | `/api/projects/{key}/runs/{id}/tests/{tid}` | 单个测试详情 (步骤、错误、附件) |
| `GET` | `/api/projects/{key}/reports/latest/{path}` | 最新报告静态文件 |
| `GET` | `/api/projects/{key}/reports/{id}/{path}` | 历史报告静态文件 |
| `GET` | `/api/projects/{key}/attachments/{aid}` | 下载附件文件 |

### 看板 & 对比

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/dashboard` | 看板聚合数据 |
| `GET` | `/api/settings` | 全局配置 + 项目概况 (含 Allure 版本) |
| `POST` | `/api/compare` | 多 Run 横向对比 |

### 其他

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/health` | 健康检查 |

## 上传处理流程

1. `POST /api/projects/{key}/runs` 上传 allure-results.zip → 返回 `202` + `run_id`
2. 后台任务:
   - 解压 zip → `runs/{run_id}/allure-results/`
   - `result_parser.py`: 解析 `*-result.json` → 写入 PostgreSQL
   - `allure_cli.py`: 调用 `npx allure awesome` 生成静态 HTML
   - `allure_cli.py`: `fix_history_urls()` 补全 history 链接
   - `cleanup.py`: 超出 `max_runs` 的旧 run 自动删除
3. 客户端轮询 `GET .../runs/{run_id}` 查状态
4. 报告通过 `GET .../reports/{run_id}/` 访问

## History 机制

Allure 3 通过 `history.jsonl` 原生管理历史数据。每次生成报告时 `appendHistory: true` 自动追加一行，驱动趋势图、flaky 检测、历史对比。

### History URL 修复

Allure 3 默认不填 history entry 的 `url` 字段，导致 History 标签链接不可点击。

`fix_history_urls()` 维护 `url_map.json` 映射文件 (allure_uuid → run_id)，处理逻辑：

1. 记录新报告 Allure UUID → run_id 映射
2. 遍历 `history.jsonl`，为已知映射的 entry 补全 `url` 字段

## 数据布局

```
/data/allure/projects/
  {project_key}/
    ├── allurerc.mjs              # Allure 配置
    ├── history.jsonl             # 历史记录
    ├── url_map.json              # allure_uuid → run_id 映射
    ├── attachments/              # 附件文件
    └── runs/
        └── {run_id}/
            ├── allure-results/   # 上传的原始结果
            └── allure-report/    # 生成的静态 HTML
```

## 数据库表

| 表 | 说明 |
|----|------|
| `projects` | 项目 (key, name, description, max_runs, created_at, updated_at) |
| `runs` | 运行记录 (id, project_key, status, branch, commit_hash, 统计, duration, error) |
| `test_results` | 测试结果 (uuid, history_id, name, status, labels/links/parameters JSONB) |
| `test_steps` | 测试步骤 (parent_step_id 自引用嵌套) |
| `test_attachments` | 附件元信息 (name, source, type, file_path, size) |

## 配置

### 环境变量

前缀 `ALLURE_`：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ALLURE_DATABASE_URL` | `postgresql+asyncpg://allure:allure@localhost:5432/allure3` | 异步连接 |
| `ALLURE_DATABASE_URL_SYNC` | `postgresql://allure:allure@localhost:5432/allure3` | 同步连接 (Alembic) |
| `ALLURE_DATA_DIR` | `/data/allure` | 数据存储根目录 |

### 项目参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `key` | 必填 | 唯一标识，`^[a-zA-Z0-9_-]+$` |
| `name` | 必填 | 显示名称 |
| `description` | — | 项目描述 |
| `max_runs` | 20 | 保留的最大 run 数 |

## 部署架构

```
Browser :80
    │
    ▼
┌─ frontend (nginx) ────────────┐
│  /              → dist/       │  Vue SPA
│  /api/*         → backend     │  API proxy
│  /docs          → backend     │  Swagger
└───────────┬───────────────────┘
            │
            ▼
┌─ backend :8000 (internal) ────┐
│  FastAPI + async SQLAlchemy   │
│  + Node.js (allure CLI)       │
└───────────┬───────────────────┘
            │
            ▼
┌─ db :5432 (internal) ─────────┐
│  PostgreSQL 16                │
└───────────────────────────────┘
```

## 技术栈

| 层 | 技术 |
|---|------|
| Web 框架 | FastAPI (async) |
| Python 环境 | uv |
| ORM | SQLAlchemy 2.0 (async) |
| 数据库 | PostgreSQL 16 |
| 迁移 | Alembic |
| 报告生成 | Allure 3 CLI (`npx allure awesome`) |
| 前端 | Vue 3 (TypeScript) |
| UI 组件 | Naive UI |
| 图表 | ECharts |
| 状态管理 | Pinia |
| 部署 | Docker Compose (Nginx + FastAPI + PostgreSQL) |

## 开发命令

```bash
# ── 后端 ──
cd backend
uv sync                                    # 安装依赖
uv run uvicorn app.main:app --reload       # 启动
uv run alembic upgrade head                # 迁移
uv add <pkg>                               # 加依赖

# ── 前端 ──
cd frontend
npm install                                # 安装依赖
npm run dev                                # 启动
npm run build                              # 构建

# ── Docker ──
docker compose up -d                       # 启动所有服务
docker compose build backend               # 重建后端
docker compose build frontend              # 重建前端
docker compose logs -f                     # 查看日志
```
