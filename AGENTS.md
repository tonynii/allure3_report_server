# Allure3 Report Service

## Overview

基于 FastAPI 的 Allure 3 测试报告平台。用户上传 pytest allure-results，平台自动生成 Allure 3 报告，按项目划分管理，报告为静态 HTML 可通过固定 URL 访问。Vue3 前端提供项目管理、报告查看、测试详情等功能。测试结果结构化存入 PostgreSQL 用于 LLM 分析。

## Tech Stack

| 层 | 技术 |
|---|------|
| Web 框架 | FastAPI (async) |
| Python 环境管理 | uv |
| ORM | SQLAlchemy 2.0 (async) |
| 数据库 | PostgreSQL 16 |
| 迁移 | Alembic |
| 报告生成 | Allure 3 CLI (npx allure awesome) |
| 前端 | Vue 3 (TypeScript, 独立项目，前后端分离) |
| 前端 UI | Naive UI + ECharts |
| 状态管理 | Pinia |
| 部署 | Docker Compose (Nginx + FastAPI + PostgreSQL) |

## Directory Structure

```
allure3-s/
├── docker-compose.yml              # PostgreSQL + Backend + Frontend
├── frontend/
│   ├── Dockerfile                  # 多阶段: node build → nginx serve
│   ├── nginx.conf                  # SPA fallback + /api/* 反向代理
│   ├── package.json
│   ├── vite.config.ts              # Vite + AutoImport + 本地代理
│   ├── tsconfig.json
│   └── src/
│       ├── main.ts                 # Vue3 入口
│       ├── App.vue                 # Naive ConfigProvider + Router
│       ├── api/                    # axios 封装: client.ts, projects.ts, reports.ts
│       ├── stores/                 # Pinia: project.ts, run.ts
│       ├── router/index.ts         # 6 条路由 (懒加载)
│       ├── views/
│       │   ├── ProjectsPage.vue    # 项目卡片网格 + 创建/删除
│       │   ├── ProjectDetail.vue   # Stats卡片 + 饼图/趋势图 + Run表格
│       │   ├── RunDetail.vue       # 测试列表 + 状态筛选 + 搜索
│       │   ├── TestDetail.vue      # 步骤树 + 错误堆栈 + 附件
│       │   └── ReportViewer.vue    # iframe 嵌入 Allure HTML
│       ├── components/
│       │   ├── AppHeader.vue       # 顶部导航
│       │   ├── StatsCards.vue      # Total/Passed/Failed/Broken/Skipped 卡片
│       │   ├── StatusTag.vue       # 彩色状态标签
│       │   ├── PieChart.vue        # 测试结果分布 (ECharts)
│       │   ├── TrendChart.vue      # 历史趋势 (ECharts)
│       │   └── StepTree.vue        # 递归步骤树
│       └── utils/                  # status.ts, format.ts
├── backend/
│   ├── Dockerfile                  # Python 3.12 + Node.js (allure CLI) + uv
│   ├── pyproject.toml              # uv 项目配置 + 依赖
│   ├── uv.lock                     # 依赖锁文件
│   ├── .env                        # 环境变量
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/0001_initial.py
│   └── app/
│       ├── __init__.py
│       ├── main.py                 # FastAPI 入口，CORS，路由注册
│       ├── config.py               # pydantic-settings 配置
│       ├── database.py             # async SQLAlchemy session
│       ├── models/
│       │   └── __init__.py         # Project, Run, TestResult, TestStep, TestAttachment
│       ├── schemas/
│       │   └── __init__.py         # Pydantic 请求/响应模型
│       ├── routers/
│       │   ├── __init__.py
│       │   ├── projects.py         # 项目 CRUD
│       │   └── reports.py          # 上传、报告生成、静态文件服务
│       └── services/
│           ├── __init__.py
│           ├── allure_cli.py       # 调用 allure awesome CLI + fix_history_urls
│           ├── result_parser.py    # 解析 allure-results JSON → 写 DB
│           └── cleanup.py          # 按 max_runs 清理旧 runs
└── scripts/
    └── upload.py                   # CLI 上传工具
```

## Development Commands

```bash
# ── Backend ──
cd backend
uv sync                          # 安装依赖
uv run uvicorn app.main:app --reload  # 启动 (localhost:8000)
uv run alembic upgrade head      # 数据库迁移
uv run alembic revision --autogenerate -m "description"
uv add <package>                 # 添加依赖
uv remove <package>

# ── Frontend ──
cd frontend
npm install                      # 安装依赖
npm run dev                      # 启动 (localhost:5173, proxy /api → :8000)
npm run build                    # 生产构建 → dist/

# ── Docker ──
docker compose up -d             # 一键启动所有服务 (localhost:80)
docker compose build backend     # 重建后端
docker compose build frontend    # 重建前端
```

## Environment Variables

通过 `.env` 文件或环境变量设置，前缀 `ALLURE_`:

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ALLURE_DATABASE_URL` | `postgresql+asyncpg://allure:allure@localhost:5432/allure3` | 异步数据库连接 |
| `ALLURE_DATABASE_URL_SYNC` | `postgresql://allure:allure@localhost:5432/allure3` | 同步连接（Alembic） |
| `ALLURE_DATA_DIR` | `/data/allure` | 数据存储根目录 |

## Data Storage Layout

```
/data/allure/projects/
  {project_key}/                    # 用户指定，如 "my-app-backend"
    ├── allurerc.mjs                # Allure 配置（historyPath、插件）
    ├── history.jsonl               # Allure 原生历史记录 (含 url 字段)
    ├── url_map.json                # allure_report_uuid → run_id 映射 (history 链接用)
    ├── attachments/                # 附件归档
    └── runs/
        ├── {run_id}/
        │   ├── allure-results/     # 上传的原始结果 JSON + 附件
        │   └── allure-report/      # 生成的静态 HTML 报告
        └── (保留最近 N 个 runs)
```

## Database Schema

### projects
| Column | Type | Notes |
|--------|------|-------|
| key | VARCHAR(100) PK | 用户指定，如 "my-app-backend" |
| name | VARCHAR(255) | 项目名称 |
| description | TEXT | |
| max_runs | INT | 保留的最大 run 数量，默认 20 |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### runs
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| project_key | FK → projects | |
| status | ENUM(processing,completed,failed) | 上传 → 后台处理 → 完成/失败 |
| branch | VARCHAR(255) | |
| commit_hash | VARCHAR(40) | |
| total/passed/failed/broken/skipped/unknown | INT | |
| duration_ms | BIGINT | |
| error_message | TEXT | 失败原因 |
| created_at | TIMESTAMPTZ | |
| completed_at | TIMESTAMPTZ | |

### test_results
每个 allure-results JSON 对应一条记录，labels/links/parameters/status_details 存为 JSONB。

### test_steps
嵌套步骤，parent_step_id 自引用。

### test_attachments
关联 test_result 或 step，文件复制到 `/data/allure/projects/{key}/attachments/`。

## API Endpoints

### 项目管理
| Method | Path | 说明 |
|--------|------|------|
| POST | /api/projects | 创建项目 |
| GET | /api/projects | 项目列表 |
| GET | /api/projects/{key} | 项目详情 |
| PUT | /api/projects/{key} | 更新项目 |
| DELETE | /api/projects/{key} | 删除项目及所有数据 |

### 报告管理
| Method | Path | 说明 |
|--------|------|------|
| POST | /api/projects/{key}/runs | 上传 allure-results.zip → 202 |
| GET | /api/projects/{key}/runs | 所有 runs 列表 |
| GET | /api/projects/{key}/runs/{id} | run 详情 + 统计 |
| GET | /api/projects/{key}/runs/{id}/tests/{tid} | 单个 test result 详情 |
| GET | /api/projects/{key}/reports/latest/{path} | 最新报告静态文件 |
| GET | /api/projects/{key}/reports/{id}/{path} | 历史报告静态文件 |

### 其他
| Method | Path | 说明 |
|--------|------|------|
| GET | /api/health | 健康检查 |

## Upload Flow

1. `POST /api/projects/{key}/runs` 上传 allure-results.zip
2. 服务返回 `202` + run_id
3. 后台任务 (FastAPI BackgroundTasks):
   - 解压 zip → `runs/{run_id}/allure-results/`
   - `result_parser.py`: 解析 `*-result.json` → 写入 PostgreSQL (test_results/steps/attachments)
   - `allure_cli.py`: 调用 `npx allure awesome` 生成静态 HTML
   - `allure_cli.py`: `fix_history_urls()` — 补全 history.jsonl 中的 url 字段，使 Allure 报告 History 标签可点击跳转到对应历史报告
   - `cleanup.py`: 超出 max_runs 的旧 run 自动删除
4. 客户端轮询 `GET .../runs/{run_id}` 查状态（status: processing → completed/failed）
5. 报告通过 `GET .../reports/{run_id}/` 访问
6. 前端 `RunDetail` 显示 DB 中的结构化数据（📊 详情按钮），`ReportViewer` 嵌入 Allure HTML（📄 报告按钮）

## History URL Fix

Allure 3 的 `history.jsonl` 中每条记录的 `url` 字段默认为空，导致报告中 History 标签链接不可点击。

**解决方案**: `fix_history_urls()` 在每次报告生成后自动维护 `url_map.json` 映射文件，将 Allure 报告的 `uuid` 映射到我们的 `run_id`，然后回填到 `history.jsonl`:

```
Before: {"uuid":"abc","url":"",...}
After:  {"uuid":"abc","url":"/api/projects/my-app/reports/our-run-id/",...}
```

## Frontend

### Pages & Routes

| Path | View | 说明 |
|------|------|------|
| `/` | `DashboardPage` | 看板主页：项目数/Runs/通过率统计 + 项目概况卡片 + 最近运行列表 |
| `/projects` | `ProjectsPage` | 项目卡片网格 + 创建/删除 |
| `/projects/:key` | `ProjectDetail` | Stats卡片 + 饼图/趋势图 + Run表格（📊详情 📄报告 🗑删除 按钮）|
| `/projects/:key/runs/:id` | `RunDetail` | 测试列表 + 状态筛选 + 关键词搜索 + 头部 🗑删除 |
| `/projects/:key/runs/:id/tests/:tid` | `TestDetail` | 步骤树 + 错误堆栈 + 附件下载 |
| `/projects/:key/reports/latest` | `ReportViewer` | iframe 嵌入最新 Allure HTML |
| `/projects/:key/reports/:id` | `ReportViewer` | iframe 嵌入历史报告 |
| `/tools` | `ToolsPage` | 上传工具：选择项目 + 拖拽上传 allure-results.zip + 状态轮询 |
| `/settings` | `SettingsPage` | 全局信息 + 项目概况表（存储空间/Runs数）+ ✏️编辑 🗑删除 |

### 侧边栏菜单

| 菜单 | 路由 | 说明 |
|------|------|------|
| 📊 看板 | `/` | Dashboard 主页 |
| 📁 项目 | `/projects` | 项目列表 |
| 🔧 工具 | `/tools` | 上传工具 |
| ⚙️ 配置 | `/settings` | 全局信息 + 项目管理 |

### 双入口设计

前端明确区分两个数据来源：

| 按钮 | 数据来源 | 行为 |
|------|----------|------|
| 📊 详情 | PostgreSQL 结构化数据 | `router.push` → RunDetail 页面 |
| 📄 报告 | Allure 静态 HTML | `window.open` 新标签 / iframe 嵌入 |

### 删除功能

| 位置 | 删除对象 | 确认方式 |
|------|---------|----------|
| ProjectsPage 项目卡片 | 项目 | `n-popconfirm` |
| ProjectDetail Run 表格 | 单个 Run | `useDialog().warning()` 模态框 |
| RunDetail 头部 | 当前 Run | `n-popconfirm` |
| SettingsPage 项目表 | 项目 | `useDialog().warning()` 模态框 |

## Deployment Architecture

```
Browser :80
    │
    ▼
┌─ frontend (nginx) ────────────┐
│  /              → dist/       │  Vue SPA (static HTML)
│  /api/*         → backend     │  API proxy
│  /docs          → backend     │  Swagger proxy
│  /openapi.json  → backend     │
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

## Key Architectural Decisions

1. **Allure CLI 调用方式**: Python 后端通过 `subprocess` 调用 `npx allure awesome`，Allure 3 是 TypeScript 工具，无 Python API
2. **History**: 使用 Allure 原生 `history.jsonl` 机制，不存数据库。每个项目一个 history.jsonl，Allure CLI 自动维护。`fix_history_urls()` 后处理补全 url 使历史链接可用
3. **报告静态服务**: 通过自定义路由 + FileResponse 直接映射文件系统路径，不使用 `allure open`
4. **数据双存储**: 原始文件（报告 HTML + JSON + 附件）存文件系统，结构化数据（test_results/steps）存 PostgreSQL，后者用于未来 LLM 分析
5. **清理策略**: 每项目最多保留 N 个 run（默认 20），history.jsonl 不限制
6. **前端分离**: Vue3 前端作为独立项目，通过 CORS 调用 REST API
7. **Nginx 反向代理**: 统一入口 `:80`，前端 SPA + /api/* 代理到 FastAPI，解决跨域和部署复杂度

## Project Key Convention

- `project_key`: 用户指定的唯一标识符，必须匹配 `^[a-zA-Z0-9_-]+$`，如 "my-app-backend"
- `run_id`: UUID，自动生成
- 上传文件: `.zip` 格式，包含 `allure-results/` 目录或直接包含 `*-result.json` 文件

## Upload Script

`scripts/upload.py` — CLI 上传工具，将本地 allure-results 打包上传并轮询直到报告生成完毕。

```bash
# 基础用法 (从 backend 目录运行)
uv run ../scripts/upload.py --project my-app ./allure-results/

# 指定服务器
uv run ../scripts/upload.py --server https://reports.example.com --project my-app ./allure-results/

# 带分支/commit
uv run ../scripts/upload.py --project my-app --branch main --commit abc1234 ./allure-results/

# 仅上传不等待
uv run ../scripts/upload.py --project my-app --no-wait ./allure-results/
```
