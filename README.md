# Allure3 Report Service

基于 FastAPI 的全托管 Allure 3 测试报告平台。用户通过 API 上传 pytest `allure-results`，平台自动生成 Allure 3 静态 HTML 报告，支持按项目划分、历史追踪、结构化数据存入 PostgreSQL 供 LLM 分析。

## 快速开始

### 环境要求

- Python 3.12+
- PostgreSQL 16
- Node.js 22 (Allure 3 CLI)
- Docker & Docker Compose (可选部署方式)

### 本地开发

```bash
# 1. 安装 uv 包管理器
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 克隆项目
git clone <repo-url> allure3-s
cd allure3-s/backend

# 3. 配置环境变量 (可选，.env 已有默认值)
cp .env.example .env
# 编辑 .env: 修改数据库连接等

# 4. 安装依赖
uv sync

# 5. 数据库迁移
uv run alembic upgrade head

# 6. 启动服务
uv run uvicorn app.main:app --reload

# 服务运行在 http://localhost:8000
# API 文档: http://localhost:8000/docs
```

### Docker Compose 部署

```bash
# 一键启动 (PostgreSQL + Backend)
docker compose up -d

# 查看日志
docker compose logs -f backend

# 停止
docker compose down

# 停止并清理数据卷
docker compose down -v
```

服务启动后：
- API: `http://localhost:8000/api/health`
- Swagger 文档: `http://localhost:8000/docs`

## 使用流程

### 使用上传脚本 (推荐)

```bash
# 从 backend 目录运行
cd backend
uv run ../scripts/upload.py --project my-app ./allure-results/

# 带更多选项
uv run ../scripts/upload.py \
  --server http://localhost:8000 \
  --project my-app \
  --branch main \
  --commit abc1234 \
  ./allure-results/

# 查看帮助
uv run ../scripts/upload.py --help
```

脚本自动完成: 打包 → 上传 → 轮询 → 输出报告 URL 和统计

### 手动 API 调用

### 1. 创建项目

```bash
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "key": "my-app",
    "name": "My Application",
    "description": "后端回归测试",
    "max_runs": 20
  }'
```

### 2. 上传测试结果

```bash
# 上传 allure-results.zip
curl -X POST http://localhost:8000/api/projects/my-app/runs \
  -F "file=@allure-results.zip" \
  -F "branch=main" \
  -F "commit_hash=abc1234"
# 返回 202 + {"id": "...", "status": "processing", ...}
```

### 3. 查询状态

```bash
curl http://localhost:8000/api/projects/my-app/runs/{run_id}
# status: "processing" → "completed" / "failed"
```

### 4. 查看报告

- 最新报告: `http://localhost:8000/api/projects/my-app/reports/latest/`
- 历史报告: `http://localhost:8000/api/projects/my-app/reports/{run_id}/`
- API 查看 run 列表: `GET /api/projects/my-app/runs`

## 报告 History 机制

Allure 3 通过 `history.jsonl` (JSON Lines 格式) 原生管理历史数据，无需数据库介入。

### 工作原理

```
每项目一个 history.jsonl 文件
    ↓
每次生成报告时 Allure CLI 自动追加一行记录
    ↓
报告中自动展现趋势图、flaky 检测、历史对比
```

### 文件结构

`/data/allure/projects/{key}/history.jsonl` — 每行一个 JSON 对象，代表一次完整 run：

```jsonl
{"uuid":"abc-123","name":"My App","timestamp":1715436800000,"knownTestCaseIds":["tc1","tc2"],"testResults":{...},"metrics":{}}
{"uuid":"def-456","name":"My App","timestamp":1715523200000,"knownTestCaseIds":["tc1","tc2","tc3"],"testResults":{...},"metrics":{}}
```

### 历史数据提供的能力

| 功能 | 数据源 |
|------|--------|
| **Trend 图表** (通过/失败趋势) | history.jsonl |
| **Duration 趋势** | history.jsonl |
| **Flaky 测试检测** | 多条历史记录对比 |
| **Test History Tab** (测试详情页) | 按 historyId 检索 |
| **Categories 趋势** | history.jsonl |

### History 生命周期

- 每次 `allure awesome` 生成报告时，`appendHistory: true` 确保自动追加
- History 数据**无限增长**，不受 `max_runs` 清理策略影响
- 删除项目时随 `rm -rf /data/allure/projects/{key}/` 一并清理
- 可通过修改 `allurerc.mjs` 中的 `appendHistory` 来控制行为

## 配置参考

### 环境变量

所有环境变量前缀 `ALLURE_`，在 `backend/.env` 或 Docker Compose 中设置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ALLURE_DATABASE_URL` | `postgresql+asyncpg://allure:allure@localhost:5432/allure3` | 异步连接 (FastAPI) |
| `ALLURE_DATABASE_URL_SYNC` | `postgresql://allure:allure@localhost:5432/allure3` | 同步连接 (Alembic) |
| `ALLURE_DATA_DIR` | `/data/allure` | 报告和数据存储根目录 |

### 项目配置

每个项目创建时可设置：

| 参数 | 默认 | 说明 |
|------|------|------|
| `key` | 必填 | 唯一标识，`^[a-zA-Z0-9_-]+$` |
| `name` | 必填 | 显示名称 |
| `description` | — | 项目描述 |
| `max_runs` | 20 | 保留的最大历史报告数 |

## 数据布局

```
/data/allure/projects/
  my-app/
    ├── allurerc.mjs              # Allure 配置 (historyPath)
    ├── history.jsonl             # 历史数据 (无限增长)
    ├── attachments/              # 附件文件
    └── runs/
        ├── 550e8400-e29b-.../    # run_id (UUID)
        │   ├── allure-results/   # 上传的原始结果
        │   └── allure-report/    # 生成的静态 HTML
        └── 6ba7b810-9dad-.../
```

## 数据库表

### projects — 项目管理
```
key (PK) | name | description | max_runs | created_at | updated_at
```

### runs — 运行记录
```
id (PK) | project_key (FK) | status | branch | commit_hash |
total/passed/failed/broken/skipped/unknown | duration_ms |
error_message | created_at | completed_at
```

### test_results — 测试用例结果 (供 LLM 分析)
```
id (PK) | run_id (FK) | uuid | history_id | name | full_name |
description | status | stage | start_time | stop_time | duration_ms |
labels (JSONB) | links (JSONB) | parameters (JSONB) | status_details (JSONB)
```

### test_steps — 测试步骤
```
id (PK) | test_result_id (FK) | parent_step_id (self-FK) |
name | status | stage | start_time | stop_time | duration_ms | status_details (JSONB)
```

### test_attachments — 附件元信息
```
id (PK) | test_result_id (FK) | step_id (FK) |
name | source | type | file_path | size
```

## API 参考

### 项目管理

| Method | Path | 说明 | Body/Query |
|--------|------|------|-----------|
| `POST` | `/api/projects` | 创建 | `{key, name, description?, max_runs?}` |
| `GET` | `/api/projects` | 列表 | — |
| `GET` | `/api/projects/{key}` | 详情 | — |
| `PUT` | `/api/projects/{key}` | 更新 | `{name?, description?, max_runs?}` |
| `DELETE` | `/api/projects/{key}` | 删除项目、数据、报告 | — |

### 报告管理

| Method | Path | 说明 | Body/Query |
|--------|------|------|-----------|
| `POST` | `/api/projects/{key}/runs` | 上传 zip → 202 | `file`, `branch?`, `commit_hash?` (multipart) |
| `GET` | `/api/projects/{key}/runs` | 列表 | — |
| `GET` | `/api/projects/{key}/runs/{id}` | 详情+统计 | — |
| `GET` | `/api/projects/{key}/runs/{id}/tests/{tid}` | 测试详情 | — |
| `GET` | `/api/projects/{key}/reports/latest/{path}` | 最新报告 | `path=""` → index.html |
| `GET` | `/api/projects/{key}/reports/{id}/{path}` | 历史报告 | `path=""` → index.html |

### 健康检查

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/health` | `{"status": "ok"}` |

## 开发指南

### uv 命令速查

```bash
uv sync          # 安装/同步依赖
uv run <cmd>     # 在 venv 中运行命令
uv add <pkg>     # 添加依赖
uv remove <pkg>  # 移除依赖
uv lock          # 更新 lock 文件
```

### 数据库迁移

```bash
# 生成迁移 (需 PostgreSQL 运行)
uv run alembic revision --autogenerate -m "描述"

# 执行迁移
uv run alembic upgrade head

# 回滚
uv run alembic downgrade -1
```

### 目录创建

服务首次运行时自动创建 `/data/allure/projects/` 目录结构。

### 安装 Allure CLI

Allure 3 CLI 需要 Node.js，在 Docker 镜像中已预装。本地开发时手动安装：

```bash
npm install -g allure
allure --version  # >= 3.0.0
```

## 架构要点

1. **Allure 调用**: Python 通过 `subprocess` 执行 `npx allure awesome`，以 project 目录为 cwd
2. **History**: 使用 Allure 原生 `history.jsonl` 机制，不存数据库
3. **报告服务**: 自定义 FastAPI 路由 + `FileResponse` 映射文件系统路径
4. **数据双存**: 原始文件存文件系统，结构化数据存 PostgreSQL (LLM 分析用)
5. **清理**: 每项目保留最近 `max_runs` 个 run，超出自动删除（文件+DB）
6. **前端分离**: 预留 Vue 3 独立前端，CORS 已开启
