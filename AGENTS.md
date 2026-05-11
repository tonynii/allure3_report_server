# Allure3 Report Service

## Overview

基于 FastAPI 的 Allure 3 测试报告平台。用户上传 pytest allure-results，平台自动生成 Allure 3 报告，按项目划分管理，报告为静态 HTML 可通过固定 URL 访问。未来计划接入 Vue3 前端，测试结果结构化存入 PostgreSQL 用于 LLM 分析。

## Tech Stack

| 层 | 技术 |
|---|------|
| Web 框架 | FastAPI (async) |
| Python 环境管理 | uv |
| ORM | SQLAlchemy 2.0 (async) |
| 数据库 | PostgreSQL 16 |
| 迁移 | Alembic |
| 报告生成 | Allure 3 CLI (npx allure awesome) |
| 前端 (未来) | Vue 3 (独立项目，前后端分离) |
| 部署 | Docker Compose |

## Directory Structure

```
allure3-s/
├── docker-compose.yml              # PostgreSQL + Backend
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
│           ├── allure_cli.py       # 调用 allure awesome CLI
│           ├── result_parser.py    # 解析 allure-results JSON → 写 DB
│           └── cleanup.py          # 按 max_runs 清理旧 runs
```

## Development Commands

```bash
# 安装依赖
cd backend
uv sync

# 运行服务
uv run uvicorn app.main:app --reload

# 数据库迁移
uv run alembic upgrade head

# 自动生成迁移
uv run alembic revision --autogenerate -m "description"

# 添加/删除依赖
uv add <package>
uv remove <package>

# Docker Compose 启动
docker compose up -d

# 清理旧 venv 重建
rm -rf .venv && uv sync
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
    ├── history.jsonl               # Allure 原生历史记录
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
   - `cleanup.py`: 超出 max_runs 的旧 run 自动删除
4. 客户端轮询 `GET .../runs/{run_id}` 查状态（status: processing → completed/failed）
5. 报告通过 `GET .../reports/{run_id}/` 访问

## Key Architectural Decisions

1. **Allure CLI 调用方式**: Python 后端通过 `subprocess` 调用 `npx allure awesome`，Allure 3 是 TypeScript 工具，无 Python API
2. **History**: 使用 Allure 原生 `history.jsonl` 机制，不存数据库。每个项目一个 history.jsonl，Allure CLI 自动维护
3. **报告静态服务**: 通过自定义路由 + FileResponse 直接映射文件系统路径，不使用 `allure open`
4. **数据双存储**: 原始文件（报告 HTML + JSON + 附件）存文件系统，结构化数据（test_results/steps）存 PostgreSQL，后者用于未来 LLM 分析
5. **清理策略**: 每项目最多保留 N 个 run（默认 20），history.jsonl 不限制
6. **前端分离**: Vue3 前端作为独立项目，通过 CORS 调用 REST API

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
