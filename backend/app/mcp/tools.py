from collections import defaultdict
from datetime import datetime

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.mcp.server import mcp
from app.database import async_session
from app.models import Project, Run, TestResult, TestStep, TestAttachment
from app.config import settings


# ── Helpers ──────────────────────────────────────────────────────

def _pass_rate(run: Run) -> float:
    return round(run.passed / run.total, 4) if run.total > 0 else 0.0


def _fmt_dt(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _report_url(project_key: str, run_id: str) -> str:
    base = settings.base_url or "http://localhost:8088"
    return f"{base}/projects/{project_key}/reports/{run_id}/"


def _err_msg(sd: dict | None) -> str | None:
    return sd.get("message") if isinstance(sd, dict) else None


def _err_trace(sd: dict | None) -> str | None:
    return sd.get("trace") if isinstance(sd, dict) else None


def _is_flaky_sd(sd: dict | None) -> bool:
    return bool(sd.get("flaky")) if isinstance(sd, dict) else False


def _is_known_sd(sd: dict | None) -> bool:
    return bool(sd.get("known")) if isinstance(sd, dict) else False


def _classify_error(message: str | None) -> str:
    if not message:
        return "Unknown"
    m = message.strip()
    if "Assertion" in m or "assert" in m.lower():
        return "AssertionError"
    if "timeout" in m.lower() or "timed out" in m.lower():
        return "TimeoutError"
    if "connection" in m.lower() or "connect" in m.lower():
        return "ConnectionError"
    if "NullPointerException" in m:
        return "NullPointerException"
    if "not found" in m.lower() or "no such file" in m.lower():
        return "NotFound"
    if "permission" in m.lower() or "forbidden" in m.lower() or "access denied" in m.lower():
        return "PermissionError"
    if "import" in m.lower() and "module" in m.lower():
        return "ImportError"
    for pfx in ("TypeError", "ValueError", "KeyError", "AttributeError", "RuntimeError", "SyntaxError"):
        if m.startswith(pfx):
            return pfx
    first_line = m.split("\n")[0][:80]
    return first_line + ("..." if len(m.split("\n")[0]) > 80 else "")


def _build_step_tree(steps: list[TestStep]) -> list["StepDetail"]:
    roots = [s for s in steps if s.parent_step_id is None]
    return [_step_detail(s) for s in roots]


def _step_detail(step: TestStep) -> "StepDetail":
    children = [_step_detail(c) for c in (step.children or [])]
    return StepDetail(
        id=str(step.id),
        name=step.name,
        status=step.status,
        duration_ms=step.duration_ms,
        status_details=step.status_details,
        children=children,
    )


# ── Output Models ───────────────────────────────────────────────

class ProjectSummary(BaseModel):
    key: str = Field(description="项目唯一标识")
    name: str = Field(description="项目名称")
    description: str | None = Field(description="项目描述")
    runs_count: int = Field(description="运行总数")
    latest_run_status: str | None = Field(description="最近一次运行状态")
    latest_run_pass_rate: float | None = Field(description="最近一次运行通过率 (0-1)")


class ProjectDetail(BaseModel):
    key: str
    name: str
    description: str | None
    max_runs: int
    runs_count: int
    recent_runs: list["RunSummary"] = Field(default_factory=list)


class RunSummary(BaseModel):
    id: str
    status: str
    branch: str | None
    commit_hash: str | None
    total: int
    passed: int
    failed: int
    broken: int
    skipped: int
    unknown: int
    pass_rate: float = Field(description="通过率 (0-1)")
    duration_ms: int | None
    created_at: str | None
    completed_at: str | None
    report_url: str | None


class RunDetail(BaseModel):
    id: str
    project_key: str
    status: str
    branch: str | None
    commit_hash: str | None
    total: int
    passed: int
    failed: int
    broken: int
    skipped: int
    unknown: int
    pass_rate: float
    duration_ms: int | None
    environment: list | None
    created_at: str | None
    completed_at: str | None
    report_url: str | None
    test_results: list["TestResultItem"] = Field(default_factory=list)


class TestResultItem(BaseModel):
    id: str
    name: str
    full_name: str | None
    status: str
    duration_ms: int | None
    history_id: str | None
    labels: list | None


class TestDetail(BaseModel):
    id: str
    uuid: str
    history_id: str | None
    full_name: str | None
    name: str
    description: str | None
    status: str
    stage: str | None
    duration_ms: int | None
    labels: list | None
    links: list | None
    parameters: list | None
    status_details: dict | None
    steps: list["StepDetail"] = Field(default_factory=list)
    attachments: list["AttachmentInfo"] = Field(default_factory=list)
    report_url: str | None


class StepDetail(BaseModel):
    id: str
    name: str
    status: str
    duration_ms: int | None
    status_details: dict | None
    children: list["StepDetail"] = Field(default_factory=list)


class AttachmentInfo(BaseModel):
    id: str
    name: str
    type: str
    size: int


class AttachmentContent(BaseModel):
    id: str = Field(description="附件 ID")
    name: str = Field(description="显示名称")
    source: str = Field(description="原始文件名")
    type: str = Field(description="MIME 类型")
    size: int = Field(description="文件大小（字节）")
    is_text: bool = Field(description="是否为可读文本内容")
    text_content: str | None = Field(description="文本内容（仅文本类附件）")
    content_truncated: bool = Field(description="内容是否因过大被截断")
    truncated_at: int | None = Field(description="截断的确切字节位置")


class FailedTestDetail(BaseModel):
    id: str
    name: str
    full_name: str | None
    status: str
    duration_ms: int | None
    error_message: str | None
    error_trace: str | None
    labels: list | None
    is_flaky: bool
    is_known: bool
    report_url: str | None


class FailureCategory(BaseModel):
    error_pattern: str = Field(description="错误模式，如 AssertionError/TimeoutError")
    count: int
    affected_tests: list[str] = Field(description="受影响的测试名列表")


class SlowTest(BaseModel):
    name: str
    duration_ms: int


class FailureAnalysis(BaseModel):
    run_id: str
    project_key: str
    total: int
    passed: int
    failed: int
    broken: int
    skipped: int
    pass_rate: float = Field(description="通过率 (0-1)")
    failure_categories: list[FailureCategory] = Field(description="按错误类型分组的失败统计")
    slow_tests: list[SlowTest] = Field(description="耗时最长的 Top 5 测试")
    flaky_tests: list[str] = Field(description="被标记为 flaky 的测试名列表")
    known_issues: list[str] = Field(description="被标记为 known issue 的测试名列表")


class RunTrendItem(BaseModel):
    run_id: str
    created_at: str | None
    total: int
    passed: int
    failed: int
    broken: int
    pass_rate: float
    duration_ms: int | None


class RunTrend(BaseModel):
    project_key: str
    runs: list[RunTrendItem]


class EnvironmentInfo(BaseModel):
    run_id: str
    project_key: str
    environment: list | None


class TestMatch(BaseModel):
    id: str
    name: str
    full_name: str | None
    status: str
    duration_ms: int | None
    run_id: str
    project_key: str
    labels: list | None


class ComparisonResult(BaseModel):
    columns: list[dict]
    summary: dict
    tests: list[dict]


# ── Tools ───────────────────────────────────────────────────────

@mcp.tool()
async def list_projects() -> list[ProjectSummary]:
    """列出所有项目及其最新运行状态和通过率。
    用于了解平台上所有项目的概况，是分析的起点。"""

    async with async_session() as db:
        result = await db.execute(select(Project).order_by(Project.created_at.desc()))
        projects = result.scalars().all()

        summaries = []
        for p in projects:
            cnt_res = await db.execute(
                select(func.count(Run.id)).where(Run.project_key == p.key)
            )
            runs_count = cnt_res.scalar() or 0

            latest_res = await db.execute(
                select(Run)
                .where(Run.project_key == p.key, Run.status == "completed")
                .order_by(Run.created_at.desc())
                .limit(1)
            )
            latest = latest_res.scalar_one_or_none()

            summaries.append(ProjectSummary(
                key=p.key,
                name=p.name,
                description=p.description,
                runs_count=runs_count,
                latest_run_status=latest.status if latest else None,
                latest_run_pass_rate=_pass_rate(latest) if latest else None,
            ))
        return summaries


@mcp.tool()
async def get_project(project_key: str) -> ProjectDetail:
    """获取项目详情，包含最近运行列表。用 project_key 指定项目。"""

    async with async_session() as db:
        project = await db.get(Project, project_key)
        if not project:
            raise ValueError(f"项目 '{project_key}' 不存在")

        cnt_res = await db.execute(
            select(func.count(Run.id)).where(Run.project_key == project_key)
        )
        runs_count = cnt_res.scalar() or 0

        recent_res = await db.execute(
            select(Run)
            .where(Run.project_key == project_key)
            .order_by(Run.created_at.desc())
            .limit(10)
        )
        recent_runs = recent_res.scalars().all()

        return ProjectDetail(
            key=project.key,
            name=project.name,
            description=project.description,
            max_runs=project.max_runs,
            runs_count=runs_count,
            recent_runs=[
                RunSummary(
                    id=str(r.id),
                    status=r.status,
                    branch=r.branch,
                    commit_hash=r.commit_hash,
                    total=r.total,
                    passed=r.passed,
                    failed=r.failed,
                    broken=r.broken,
                    skipped=r.skipped,
                    unknown=r.unknown,
                    pass_rate=_pass_rate(r),
                    duration_ms=r.duration_ms,
                    created_at=_fmt_dt(r.created_at),
                    completed_at=_fmt_dt(r.completed_at),
                    report_url=_report_url(project_key, str(r.id)),
                )
                for r in recent_runs
            ],
        )


@mcp.tool()
async def list_runs(
    project_key: str,
    limit: int = Field(default=10, description="返回的运行数量，默认10"),
    status: str | None = Field(default=None, description="按状态筛选: completed/processing/failed"),
) -> list[RunSummary]:
    """列出项目的运行历史。返回最近的运行列表，可按状态筛选。"""

    async with async_session() as db:
        project = await db.get(Project, project_key)
        if not project:
            raise ValueError(f"项目 '{project_key}' 不存在")

        q = select(Run).where(Run.project_key == project_key).order_by(Run.created_at.desc())
        if status:
            q = q.where(Run.status == status)
        q = q.limit(min(limit, 50))

        result = await db.execute(q)
        runs = result.scalars().all()

        return [
            RunSummary(
                id=str(r.id),
                status=r.status,
                branch=r.branch,
                commit_hash=r.commit_hash,
                total=r.total,
                passed=r.passed,
                failed=r.failed,
                broken=r.broken,
                skipped=r.skipped,
                unknown=r.unknown,
                pass_rate=_pass_rate(r),
                duration_ms=r.duration_ms,
                created_at=_fmt_dt(r.created_at),
                completed_at=_fmt_dt(r.completed_at),
                report_url=_report_url(project_key, str(r.id)),
            )
            for r in runs
        ]


@mcp.tool()
async def get_run(project_key: str, run_id: str) -> RunDetail:
    """获取某次运行的完整详情，包含所有测试结果摘要。
    用于了解整体运行概况和定位问题测试。"""

    async with async_session() as db:
        run = await db.get(Run, run_id)
        if not run or run.project_key != project_key:
            raise ValueError(f"运行 '{run_id}' 在项目 '{project_key}' 中不存在")

        tr_res = await db.execute(
            select(TestResult)
            .where(TestResult.run_id == run.id)
            .order_by(TestResult.name)
        )
        test_results = tr_res.scalars().all()

        return RunDetail(
            id=str(run.id),
            project_key=run.project_key,
            status=run.status,
            branch=run.branch,
            commit_hash=run.commit_hash,
            total=run.total,
            passed=run.passed,
            failed=run.failed,
            broken=run.broken,
            skipped=run.skipped,
            unknown=run.unknown,
            pass_rate=_pass_rate(run),
            duration_ms=run.duration_ms,
            environment=run.environment,
            created_at=_fmt_dt(run.created_at),
            completed_at=_fmt_dt(run.completed_at),
            report_url=_report_url(project_key, run_id),
            test_results=[
                TestResultItem(
                    id=str(tr.id),
                    name=tr.name,
                    full_name=tr.full_name,
                    status=tr.status,
                    duration_ms=tr.duration_ms,
                    history_id=tr.history_id,
                    labels=tr.labels,
                )
                for tr in test_results
            ],
        )


@mcp.tool()
async def list_failed_tests(project_key: str, run_id: str) -> list[FailedTestDetail]:
    """获取某次运行中所有失败/异常测试的详细信息。
    返回每个失败测试的错误消息、堆栈跟踪和标签信息。
    这是分析失败根因的核心工具，通常在 get_run 之后调用。"""

    async with async_session() as db:
        run = await db.get(Run, run_id)
        if not run or run.project_key != project_key:
            raise ValueError(f"运行 '{run_id}' 在项目 '{project_key}' 中不存在")

        result = await db.execute(
            select(TestResult)
            .where(TestResult.run_id == run.id, TestResult.status.in_(["failed", "broken"]))
            .order_by(TestResult.name)
        )
        failed_tests = result.scalars().all()

        return [
            FailedTestDetail(
                id=str(t.id),
                name=t.name,
                full_name=t.full_name,
                status=t.status,
                duration_ms=t.duration_ms,
                error_message=_err_msg(t.status_details),
                error_trace=_err_trace(t.status_details),
                labels=t.labels,
                is_flaky=_is_flaky_sd(t.status_details),
                is_known=_is_known_sd(t.status_details),
                report_url=_report_url(project_key, run_id),
            )
            for t in failed_tests
        ]


@mcp.tool()
async def get_test_detail(project_key: str, run_id: str, test_id: str) -> TestDetail:
    """获取单个测试的完整详情，包括步骤树、错误堆栈和附件列表。
    用于深入分析某个具体失败测试。"""

    async with async_session() as db:
        run = await db.get(Run, run_id)
        if not run or run.project_key != project_key:
            raise ValueError(f"运行 '{run_id}' 在项目 '{project_key}' 中不存在")

        result = await db.execute(
            select(TestResult)
            .where(TestResult.id == test_id, TestResult.run_id == run.id)
            .options(
                selectinload(TestResult.steps).selectinload(TestStep.children).selectinload(TestStep.children),
                selectinload(TestResult.steps).selectinload(TestStep.attachments),
                selectinload(TestResult.attachments),
            )
        )
        tr = result.unique().scalar_one_or_none()
        if not tr:
            raise ValueError(f"测试 '{test_id}' 不存在")

        steps = _build_step_tree(list(tr.steps) if tr.steps else [])
        attachments = [
            AttachmentInfo(id=str(a.id), name=a.name, type=a.type, size=a.size)
            for a in (tr.attachments or [])
        ]

        return TestDetail(
            id=str(tr.id),
            uuid=tr.uuid,
            history_id=tr.history_id,
            full_name=tr.full_name,
            name=tr.name,
            description=tr.description,
            status=tr.status,
            stage=tr.stage,
            duration_ms=tr.duration_ms,
            labels=tr.labels,
            links=tr.links,
            parameters=tr.parameters,
            status_details=tr.status_details,
            steps=steps,
            attachments=attachments,
            report_url=_report_url(project_key, run_id),
        )


@mcp.tool()
async def analyze_failures(project_key: str, run_id: str) -> FailureAnalysis:
    """对某次运行进行智能失败分析。
    自动归类失败模式（按错误类型分组），识别 Flaky 测试、已知问题和慢测试。
    这是失败分析的推荐入口，之后可用 get_test_detail 查看具体详情。"""

    async with async_session() as db:
        run = await db.get(Run, run_id)
        if not run or run.project_key != project_key:
            raise ValueError(f"运行 '{run_id}' 在项目 '{project_key}' 中不存在")

        result = await db.execute(
            select(TestResult).where(TestResult.run_id == run.id)
        )
        all_tests = result.scalars().all()

        failed_tests = [t for t in all_tests if t.status in ("failed", "broken")]
        error_categories: dict[str, list[str]] = defaultdict(list)
        flaky_tests: list[str] = []
        known_issues: list[str] = []

        for t in failed_tests:
            msg = _err_msg(t.status_details)
            pattern = _classify_error(msg)
            error_categories[pattern].append(t.name or "")
            if _is_flaky_sd(t.status_details):
                flaky_tests.append(t.name or "")
            if _is_known_sd(t.status_details):
                known_issues.append(t.name or "")

        categories = [
            FailureCategory(
                error_pattern=name,
                count=len(tests),
                affected_tests=tests[:10],
            )
            for name, tests in sorted(
                error_categories.items(), key=lambda x: len(x[1]), reverse=True
            )
        ]

        sorted_by_dur = sorted(all_tests, key=lambda t: t.duration_ms or 0, reverse=True)
        slow_tests = [
            SlowTest(name=t.name or t.full_name or str(t.id), duration_ms=t.duration_ms or 0)
            for t in sorted_by_dur[:5]
        ]

        return FailureAnalysis(
            run_id=str(run.id),
            project_key=project_key,
            total=run.total,
            passed=run.passed,
            failed=run.failed,
            broken=run.broken,
            skipped=run.skipped,
            pass_rate=_pass_rate(run),
            failure_categories=categories,
            slow_tests=slow_tests,
            flaky_tests=flaky_tests,
            known_issues=known_issues,
        )


@mcp.tool()
async def compare_runs(
    run_ids: list[dict] = Field(description="运行列表，格式: [{project: 项目key, run: run_id}]"),
) -> ComparisonResult:
    """对比多次运行的测试结果，按 historyId 匹配同一测试在不同 Run 中的状态。
    返回 all_pass/all_fail/mixed/flaky 分类和详细对比矩阵。"""

    if len(run_ids) < 2:
        raise ValueError("至少需要 2 个 Run 进行对比")

    async with async_session() as db:
        run_data = []
        for item in run_ids:
            r = await db.get(Run, item["run"])
            if not r or r.project_key != item["project"]:
                raise ValueError(f"运行 '{item['run']}' 在项目 '{item['project']}' 中不存在")
            trs = await db.execute(
                select(TestResult).where(TestResult.run_id == r.id)
            )
            tests = {t.history_id: t for t in trs.scalars().all() if t.history_id}
            run_data.append({
                "run_id": str(r.id),
                "project": r.project_key,
                "branch": r.branch or "",
                "tests": tests,
            })

        all_ids: set[str] = set()
        for rd in run_data:
            all_ids.update(rd["tests"].keys())

        columns = [
            {
                "run_id": rd["run_id"],
                "project": rd["project"],
                "branch": rd["branch"],
                "total": len(rd["tests"]),
            }
            for rd in run_data
        ]

        summary = {"all_pass": 0, "all_fail": 0, "mixed": 0, "flaky": 0}
        tests_out = []

        for hid in sorted(all_ids):
            results = {}
            statuses = []
            names: set[str] = set()

            for rd in run_data:
                tr = rd["tests"].get(hid)
                if tr:
                    results[rd["run_id"]] = {
                        "status": tr.status,
                        "duration_ms": tr.duration_ms,
                        "error_message": _err_msg(tr.status_details),
                    }
                    statuses.append(tr.status)
                    names.add(tr.name)

            unique = set(statuses)
            if unique == {"passed"}:
                cat = "all_pass"
            elif unique <= {"failed", "broken"}:
                cat = "all_fail"
            else:
                cat = "flaky" if "failed" in unique and "passed" in unique else "mixed"
            summary[cat] += 1

            tests_out.append({
                "historyId": hid,
                "name": sorted(names)[0] if names else hid[:16],
                "results": results,
                "summary": cat,
            })

        return ComparisonResult(columns=columns, summary=summary, tests=tests_out)


@mcp.tool()
async def search_tests(
    project_key: str,
    keyword: str = Field(default="", description="搜索关键词（匹配测试名或全限定名）"),
    status: str | None = Field(default=None, description="按状态筛选: passed/failed/broken/skipped"),
    run_id: str | None = Field(default=None, description="限定在某次运行中搜索"),
    limit: int = Field(default=20, description="返回结果数量上限"),
) -> list[TestMatch]:
    """跨运行搜索测试用例，支持按关键词、状态筛选。
    适用于查找特定功能模块的测试或追踪某个测试的历史表现。"""

    async with async_session() as db:
        project = await db.get(Project, project_key)
        if not project:
            raise ValueError(f"项目 '{project_key}' 不存在")

        q = select(TestResult)

        if run_id:
            q = q.where(TestResult.run_id == run_id)
        else:
            run_q = select(Run.id).where(Run.project_key == project_key)
            q = q.where(TestResult.run_id.in_(run_q))

        if status:
            q = q.where(TestResult.status == status)
        if keyword:
            kw = f"%{keyword}%"
            q = q.where(
                TestResult.name.ilike(kw) | TestResult.full_name.ilike(kw)
            )

        q = q.order_by(TestResult.name).limit(min(limit, 100))
        result = await db.execute(q)
        tests = result.scalars().all()

        matches = []
        for t in tests:
            run = await db.get(Run, t.run_id)
            matches.append(TestMatch(
                id=str(t.id),
                name=t.name,
                full_name=t.full_name,
                status=t.status,
                duration_ms=t.duration_ms,
                run_id=str(t.run_id),
                project_key=run.project_key if run else project_key,
                labels=t.labels,
            ))
        return matches


@mcp.tool()
async def get_run_trend(
    project_key: str,
    limit: int = Field(default=10, description="返回最近 N 次运行"),
) -> RunTrend:
    """获取项目最近 N 次运行的通过率趋势数据。
    用于判断项目健康度走向（好转/恶化/稳定）。"""

    async with async_session() as db:
        project = await db.get(Project, project_key)
        if not project:
            raise ValueError(f"项目 '{project_key}' 不存在")

        result = await db.execute(
            select(Run)
            .where(Run.project_key == project_key, Run.status == "completed")
            .order_by(Run.created_at.desc())
            .limit(min(limit, 50))
        )
        runs = result.scalars().all()

        items = [
            RunTrendItem(
                run_id=str(r.id),
                created_at=_fmt_dt(r.created_at),
                total=r.total,
                passed=r.passed,
                failed=r.failed,
                broken=r.broken,
                pass_rate=_pass_rate(r),
                duration_ms=r.duration_ms,
            )
            for r in runs
        ]

        return RunTrend(project_key=project_key, runs=list(reversed(items)))


@mcp.tool()
async def get_environment(project_key: str, run_id: str) -> EnvironmentInfo:
    """获取某次运行的环境信息（操作系统、浏览器、环境变量等）。
    用于排查环境导致的问题。"""

    async with async_session() as db:
        run = await db.get(Run, run_id)
        if not run or run.project_key != project_key:
            raise ValueError(f"运行 '{run_id}' 在项目 '{project_key}' 中不存在")

        return EnvironmentInfo(
            run_id=str(run.id),
            project_key=project_key,
            environment=run.environment,
        )


TEXT_MIME_TYPES = {
    "text/plain", "text/html", "text/xml", "text/csv", "text/markdown",
    "application/json", "application/xml", "application/javascript",
    "application/yaml", "application/x-yaml", "application/toml",
}
MAX_TEXT_SIZE = 500 * 1024


@mcp.tool()
async def get_attachment_content(
    project_key: str,
    attachment_id: str,
) -> AttachmentContent:
    """获取测试附件的实际内容。
    对于文本类附件（日志、JSON、XML 等），直接返回可读的文本内容。
    用于 LLM 分析失败测试时读取请求/响应体、日志等上下文信息。"""

    from pathlib import Path

    async with async_session() as db:
        att = await db.get(TestAttachment, attachment_id)
        if not att:
            raise ValueError(f"附件 '{attachment_id}' 不存在")

        if not att.file_path:
            return AttachmentContent(
                id=str(att.id),
                name=att.name,
                source=att.source,
                type=att.type,
                size=att.size,
                is_text=False,
                text_content=None,
                content_truncated=False,
                truncated_at=None,
            )

        fp = Path(att.file_path)
        if not fp.exists():
            return AttachmentContent(
                id=str(att.id),
                name=att.name,
                source=att.source,
                type=att.type,
                size=att.size,
                is_text=False,
                text_content=None,
                content_truncated=False,
                truncated_at=None,
            )

        actual_size = fp.stat().st_size
        is_text = att.type in TEXT_MIME_TYPES

        if not is_text:
            return AttachmentContent(
                id=str(att.id),
                name=att.name,
                source=att.source,
                type=att.type,
                size=actual_size,
                is_text=False,
                text_content=None,
                content_truncated=False,
                truncated_at=None,
            )

        raw = fp.read_bytes()
        content_truncated = len(raw) > MAX_TEXT_SIZE
        if content_truncated:
            raw = raw[:MAX_TEXT_SIZE]

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return AttachmentContent(
                id=str(att.id),
                name=att.name,
                source=att.source,
                type=att.type,
                size=actual_size,
                is_text=False,
                text_content=None,
                content_truncated=False,
                truncated_at=None,
            )

        return AttachmentContent(
            id=str(att.id),
            name=att.name,
            source=att.source,
            type=att.type,
            size=actual_size,
            is_text=True,
            text_content=text,
            content_truncated=content_truncated,
            truncated_at=MAX_TEXT_SIZE if content_truncated else None,
        )
