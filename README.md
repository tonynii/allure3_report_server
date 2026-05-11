# Allure3 Report Service

基于 FastAPI 的全托管 Allure 3 测试报告平台。用户通过 API 或 Web 界面上传 pytest `allure-results`，平台自动生成 Allure 3 静态 HTML 报告，支持按项目划分、历史追踪、测试详情浏览、附件下载。测试结果结构化存入 PostgreSQL 供 LLM 分析。

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
# 后端
cd backend
uv sync                                      # 安装依赖
uv run alembic upgrade head                  # 数据库迁移
uv run uvicorn app.main:app --reload         # 启动 API (localhost:8000)

# 前端
cd frontend
npm install                                  # 安装依赖
npm run dev                                  # 启动前端 (localhost:5173)
```

## 使用流程

### Web 界面

1. 打开 `http://localhost`，点击「创建项目」创建项目
2. 进入项目点击「上传报告」选择本地 `allure-results.zip`
3. 等待报告生成完毕，点击「📊 详情」查看结构化测试数据，点击「📄 报告」查看 Allure HTML 报告

### CLI 上传脚本

```bash
cd backend
uv run ../scripts/upload.py --project my-app ./allure-results/
uv run ../scripts/upload.py -s https://reports.example.com -p my-app -b main ./allure-results/
uv run ../scripts/upload.py --project my-app --no-wait ./allure-results/
```

### curl 手动调用

```bash
# 创建项目
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"key":"my-app","name":"My Application","max_runs":20}'

# 上传结果
curl -X POST http://localhost:8000/api/projects/my-app/runs \
  -F "file=@allure-results.zip" -F "branch=main"

# 查询状态
curl http://localhost:8000/api/projects/my-app/runs/{run_id}
```

## 前端页面

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | 项目列表 | 项目卡片网格 + 创建/删除 |
| `/projects/:key` | 项目详情 | Stats 卡片 + 饼图/趋势图 + Run 表格 + 上传 |
| `/projects/:key/runs/:id` | Run 详情 | 测试列表 + 状态筛选 + 关键词搜索 |
| `/projects/:key/runs/:id/tests/:tid` | 测试详情 | 步骤树 + 错误堆栈 + 附件下载 |
| `/projects/:key/reports/latest` | 最新报告 | iframe 嵌入 Allure HTML |
| `/projects/:key/reports/:id` | 历史报告 | iframe 嵌入历史 Allure HTML |

### 双入口设计

| 按钮 | 数据来源 | 点击行为 |
|------|----------|----------|
| 📊 详情 | PostgreSQL 结构化数据 | 跳转 RunDetail / TestDetail 页面 |
| 📄 报告 | Allure 静态 HTML | 新标签打开 / iframe 嵌入 |

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
| `GET` | `/api/projects/{key}/runs/{id}/tests/{tid}` | 单个测试详情 (步骤、错误、附件) |
| `GET` | `/api/projects/{key}/reports/latest/{path}` | 最新报告静态文件 |
| `GET` | `/api/projects/{key}/reports/{id}/{path}` | 历史报告静态文件 |
| `GET` | `/api/projects/{key}/attachments/{aid}` | 下载附件文件 |

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

### 工作原理

Allure 3 通过 `history.jsonl` 原生管理历史数据，每个项目一个文件：

```
每项目一个 history.jsonl
    ↓
每次生成报告 Allure CLI 自动追加一行
    ↓
报告中自动展现：趋势图、flaky 检测、历史对比
```

### History URL 修复

Allure 3 默认不填 history entry 的 `url` 字段，导致 History 标签链接不可点击。

`fix_history_urls()` 在每次报告生成后自动处理：
1. 记录 Allure report UUID → run_id 映射 (`url_map.json`)
2. 遍历 `history.jsonl` 所有行，为已知映射的 entry 补全 `url` 字段

```json
// Before
{"uuid":"abc","url":"","testResults":{...}}
// After
{"uuid":"abc","url":"/api/projects/my-app/reports/our-run-id/",...}
```

### History 生命周期

- 每次报告生成时 `appendHistory: true` 自动追加
- History 数据**无限增长**，不受 `max_runs` 清理策略影响
- 删除项目时一并清理

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

前缀 `ALLURE_`，在 `backend/.env` 或 Docker Compose 中设置：

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
uv run alembic revision --autogenerate -m "msg"
uv add <pkg>                               # 加依赖

# ── 前端 ──
cd frontend
npm install                                # 安装依赖
npm run dev                                # 启动
npm run build                              # 构建

# ── Docker ──
docker compose up -d                       # 启动
docker compose build backend               # 重建后端
docker compose build frontend              # 重建前端
docker compose logs -f                     # 查看日志
```
