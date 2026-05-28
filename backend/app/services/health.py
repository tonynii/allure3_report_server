import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Run, TestResult, FailurePattern

logger = logging.getLogger(__name__)


async def compute_health(project_key: str, db: AsyncSession) -> dict:
    indicators = {}
    now = datetime.now(timezone.utc)

    # 1. Pass rate
    recent_run = await db.execute(
        select(Run)
        .where(Run.project_key == project_key, Run.status == "completed")
        .order_by(Run.created_at.desc())
        .limit(1)
    )
    run = recent_run.scalar_one_or_none()
    pass_rate = run.passed / run.total if run and run.total > 0 else 0.0
    indicators["pass_rate"] = {
        "name": "通过率",
        "raw_value": round(pass_rate, 4),
        "score": round(pass_rate * 100, 1),
        "weight": 0.30,
        "threshold": 0.90,
        "status": _status(pass_rate, 0.90),
    }

    # 2. Stability (stddev of last 10 pass rates)
    last_10_result = await db.execute(
        select(Run)
        .where(Run.project_key == project_key, Run.status == "completed")
        .order_by(Run.created_at.desc())
        .limit(10)
    )
    last_runs = last_10_result.scalars().all()
    pass_rates = [r.passed / r.total for r in last_runs if r.total > 0]
    stddev = _stdev(pass_rates) if len(pass_rates) >= 3 else 0.0
    stability_score = max(0, 100 - stddev * 2000)
    indicators["stability"] = {
        "name": "稳定性指数",
        "raw_value": round(stddev, 4),
        "score": round(stability_score, 1),
        "weight": 0.20,
        "threshold": 0.05,
        "status": _status(stddev, 0.05, reverse=True),
    }

    # 3. Fragility (flaky ratio)
    total_count = await db.scalar(
        select(func.count(TestResult.id)).where(
            TestResult.run_id.in_(
                select(Run.id).where(Run.project_key == project_key, Run.status == "completed")
            )
        )
    ) or 0
    flaky_count = await db.scalar(
        select(func.count(TestResult.id)).where(
            TestResult.run_id.in_(
                select(Run.id).where(Run.project_key == project_key, Run.status == "completed")
            ),
            TestResult.status_details["flaky"].astext == "true",
        )
    ) or 0
    flaky_ratio = flaky_count / total_count if total_count > 0 else 0.0
    fragility_score = max(0, 100 - flaky_ratio * 2000)
    indicators["fragility"] = {
        "name": "脆弱性指数",
        "raw_value": round(flaky_ratio, 4),
        "score": round(fragility_score, 1),
        "weight": 0.15,
        "threshold": 0.05,
        "status": _status(flaky_ratio, 0.05, reverse=True),
    }

    # 4. Recovery rate (avg runs to resolve, from failure_patterns)
    resolved_q = await db.execute(
        select(FailurePattern).where(
            FailurePattern.project_key == project_key,
            FailurePattern.last_status == "resolved",
            FailurePattern.resolved_at.isnot(None),
        )
    )
    resolved_patterns = resolved_q.scalars().all()
    recovery_score = 100.0
    avg_recovery = 0.0
    if resolved_patterns:
        total_runs = 0
        count = 0
        for p in resolved_patterns:
            runs_q = await db.execute(
                select(func.count(Run.id)).where(
                    Run.project_key == project_key,
                    Run.status == "completed",
                    Run.created_at >= p.first_seen,
                    Run.created_at <= p.resolved_at,
                )
            )
            runs_between = runs_q.scalar() or 0
            total_runs += runs_between
            count += 1
        avg_recovery = total_runs / count if count > 0 else 0.0
    recovery_score = max(0, 100 - avg_recovery * 25)
    indicators["recovery_rate"] = {
        "name": "修复速度",
        "raw_value": round(avg_recovery, 1),
        "score": round(recovery_score, 1),
        "weight": 0.15,
        "threshold": 3,
        "status": _status(avg_recovery, 3, reverse=True),
    }

    # 5. Relapse rate
    total_patterns = await db.scalar(
        select(func.count(FailurePattern.id)).where(FailurePattern.project_key == project_key)
    ) or 0
    reappeared_count = await db.scalar(
        select(func.count(FailurePattern.id)).where(
            FailurePattern.project_key == project_key,
            FailurePattern.last_status == "reappeared",
        )
    ) or 0
    relapse_ratio = reappeared_count / total_patterns if total_patterns > 0 else 0.0
    relapse_score = max(0, 100 - relapse_ratio * 500)
    indicators["relapse_rate"] = {
        "name": "复发率",
        "raw_value": round(relapse_ratio, 4),
        "score": round(relapse_score, 1),
        "weight": 0.10,
        "threshold": 0.20,
        "status": _status(relapse_ratio, 0.20, reverse=True),
    }

    # 6. Slow test ratio
    percentile_q = await db.execute(
        select(func.percentile_cont(0.95).within_group(TestResult.duration_ms)).where(
            TestResult.run_id.in_(
                select(Run.id).where(
                    Run.project_key == project_key,
                    Run.status == "completed",
                    Run.created_at > now.replace(day=now.day - 30),
                )
            ),
            TestResult.duration_ms.isnot(None),
        )
    )
    p95 = (percentile_q.scalar() or 0) / 1.0
    if p95 and p95 > 0:
        above_p95 = await db.scalar(
            select(func.count(TestResult.id)).where(
                TestResult.run_id.in_(
                    select(Run.id).where(
                        Run.project_key == project_key,
                        Run.status == "completed",
                        Run.created_at > now.replace(day=now.day - 30),
                    )
                ),
                TestResult.duration_ms > p95,
                TestResult.duration_ms.isnot(None),
            )
        ) or 0
        recent_total = await db.scalar(
            select(func.count(TestResult.id)).where(
                TestResult.run_id.in_(
                    select(Run.id).where(
                        Run.project_key == project_key,
                        Run.status == "completed",
                        Run.created_at > now.replace(day=now.day - 30),
                    )
                )
            )
        ) or 1
        slow_ratio = above_p95 / recent_total
    else:
        slow_ratio = 0.0
    slow_score = max(0, 100 - slow_ratio * 1000)
    indicators["slow_ratio"] = {
        "name": "慢测试占比",
        "raw_value": round(slow_ratio, 4),
        "score": round(slow_score, 1),
        "weight": 0.10,
        "threshold": 0.10,
        "status": _status(slow_ratio, 0.10, reverse=True),
    }

    total_score = sum(ind["score"] * ind["weight"] for ind in indicators.values())
    grade = _grade(total_score)
    trend = _trend(pass_rates)
    alerts = _detect_degradation(last_runs)

    return {
        "project_key": project_key,
        "grade": grade,
        "total_score": round(total_score, 1),
        "indicators": list(indicators.values()),
        "alerts": alerts,
        "trend": trend,
    }


def _stdev(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return variance ** 0.5


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _status(value: float, threshold: float, reverse: bool = False) -> str:
    bad = value < threshold if not reverse else value > threshold
    if bad:
        margin = abs(value - threshold) / max(threshold, 0.001)
        if margin > 0.5:
            return "critical"
        return "warning"
    return "good"


def _trend(pass_rates: list[float]) -> str:
    if len(pass_rates) < 3:
        return "stable"
    recent_half = pass_rates[: len(pass_rates) // 2]
    older_half = pass_rates[len(pass_rates) // 2:]
    if not recent_half or not older_half:
        return "stable"
    recent_avg = sum(recent_half) / len(recent_half)
    older_avg = sum(older_half) / len(older_half)
    if older_avg == 0:
        return "improving" if recent_avg > 0 else "stable"
    change = (recent_avg - older_avg) / older_avg
    if change > 0.03:
        return "improving"
    if change < -0.03:
        return "worsening"
    return "stable"


def _detect_degradation(last_runs: list[Run]) -> list[dict]:
    alerts = []
    if not last_runs or len(last_runs) < 3:
        return alerts

    recent_scores = [
        r.passed / r.total if r.total > 0 else 0.0
        for r in reversed(last_runs[-3:])
    ]
    if _is_monotonic_decreasing(recent_scores):
        drop = abs(recent_scores[-1] - recent_scores[0])
        if drop >= 0.02:
            alerts.append({
                "indicator": "通过率",
                "severity": "critical" if drop >= 0.05 else "warning",
                "consecutive_drops": 3,
                "total_drop": round(drop, 4),
            })
    return alerts


def _is_monotonic_decreasing(values: list[float]) -> bool:
    if len(values) < 2:
        return False
    for i in range(1, len(values)):
        if values[i] >= values[i - 1]:
            return False
    return True
