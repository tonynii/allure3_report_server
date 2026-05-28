from datetime import datetime, timezone
import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FailurePattern, TestResult, Run
from app.services.failure_fingerprint import build_fingerprint
from app.config import settings

logger = logging.getLogger(__name__)

_HAS_EMBEDDING = bool(settings.embedding_base_url and settings.embedding_api_key)


class MatchResult:
    def __init__(self, pattern_id: str | None, match_tier: str, confidence: float):
        self.matched_pattern_id = pattern_id
        self.match_tier = match_tier
        self.confidence = confidence


async def sync_run_failures(run_id: str, project_key: str, db: AsyncSession) -> list[MatchResult]:
    result_q = await db.execute(
        select(TestResult).where(TestResult.run_id == run_id, TestResult.status.in_(["failed", "broken"]))
    )
    failed_tests = result_q.scalars().all()
    if not failed_tests:
        return []

    results: list[MatchResult] = []
    seen_sigs: set[str] = set()

    for tr in failed_tests:
        fp = build_fingerprint(tr)
        sig = fp["signature_hash"]
        if sig in seen_sigs:
            continue
        seen_sigs.add(sig)

        match_result = await _match_or_create(fp, project_key, db)
        results.append(match_result)

    await _mark_resolved(project_key, seen_sigs, db)

    return results


async def _match_or_create(fp: dict, project_key: str, db: AsyncSession) -> MatchResult:
    now = datetime.now(timezone.utc)

    # Layer 1: exact match
    exact_q = await db.execute(
        select(FailurePattern).where(
            FailurePattern.project_key == project_key,
            FailurePattern.signature_hash == fp["signature_hash"],
        )
    )
    if pattern := exact_q.scalar_one_or_none():
        pattern.occurrence_count += 1
        pattern.last_seen = now
        pattern.last_status = "active"
        pattern.confidence = min(pattern.confidence + 0.05, 1.0)
        return MatchResult(str(pattern.id), "exact", 0.95)

    # Layer 2: structural match
    structural_q = await db.execute(
        select(FailurePattern).where(
            FailurePattern.project_key == project_key,
            FailurePattern.error_type == fp["error_type"],
        )
    )
    for candidate in structural_q.scalars().all():
        if _structural_similarity(fp, candidate) > 0.7:
            candidate.occurrence_count += 1
            candidate.last_seen = now
            candidate.last_status = "active"
            candidate.confidence = min(candidate.confidence + 0.03, 1.0)
            return MatchResult(str(candidate.id), "structural", 0.75)

    # Layer 3: semantic match (optional)
    if _HAS_EMBEDDING and fp.get("raw_message"):
        semantic_q = await db.execute(
            select(FailurePattern).where(
                FailurePattern.project_key == project_key,
                FailurePattern.last_status != "resolved",
            )
        )
        match = await _semantic_match(fp, semantic_q.scalars().all())
        if match:
            match.occurrence_count += 1
            match.last_seen = now
            match.last_status = "active"
            match.confidence = min(match.confidence + 0.02, 1.0)
            return MatchResult(str(match.id), "semantic", 0.6)

    # New pattern
    new_p = FailurePattern(
        project_key=project_key,
        signature_hash=fp["signature_hash"],
        error_type=fp["error_type"],
        error_location=fp.get("error_location"),
        error_exemplar=fp.get("raw_message", "")[:2000] if fp.get("raw_message") else None,
        failure_modality=fp.get("failure_modality"),
        first_seen=now,
        last_seen=now,
        occurrence_count=1,
        last_status="active",
        confidence=0.1,
    )
    db.add(new_p)
    await db.flush()
    return MatchResult(str(new_p.id), "new", 0.0)


async def _semantic_match(fp: dict, candidates: list[FailurePattern]) -> FailurePattern | None:
    from app.services.embedding import embed_text, cosine_similarity

    msg = fp.get("raw_message", "")
    if not msg:
        return None
    try:
        fp_vec = await embed_text(msg)
        if not fp_vec:
            return None
        best = None
        best_score = 0.0
        for c in candidates:
            if not c.error_exemplar:
                continue
            c_vec = await embed_text(c.error_exemplar)
            if not c_vec:
                continue
            score = cosine_similarity(fp_vec, c_vec)
            if score > best_score:
                best_score = score
                best = c
        if best_score > 0.85:
            return best
    except Exception as e:
        logger.warning("Semantic matching failed: %s", e)
    return None


async def _mark_resolved(project_key: str, active_sigs: set[str], db: AsyncSession):
    now = datetime.now(timezone.utc)
    existing_q = await db.execute(
        select(FailurePattern).where(
            FailurePattern.project_key == project_key,
            FailurePattern.last_status == "active",
        )
    )
    for p in existing_q.scalars().all():
        if p.signature_hash not in active_sigs:
            if p.resolved_at is None:
                p.last_status = "resolved"
                p.resolved_at = now
                logger.info("Marked pattern %s (%s) as resolved", p.id, p.error_type)


async def query_failure_kb(project_key: str, signature_hash: str, db: AsyncSession) -> list[dict]:
    q = await db.execute(
        select(FailurePattern).where(
            FailurePattern.project_key == project_key,
            FailurePattern.signature_hash == signature_hash,
        )
    )
    patterns = q.scalars().all()
    return [_pattern_to_dict(p) for p in patterns]


async def get_kb_overview(project_key: str, db: AsyncSession) -> dict:
    from sqlalchemy import func

    total_q = await db.execute(
        select(func.count(FailurePattern.id)).where(FailurePattern.project_key == project_key)
    )
    total = total_q.scalar() or 0
    active_q = await db.execute(
        select(func.count(FailurePattern.id)).where(
            FailurePattern.project_key == project_key, FailurePattern.last_status == "active"
        )
    )
    active = active_q.scalar() or 0
    resolved_q = await db.execute(
        select(func.count(FailurePattern.id)).where(
            FailurePattern.project_key == project_key, FailurePattern.last_status == "resolved"
        )
    )
    resolved = resolved_q.scalar() or 0
    reappeared_q = await db.execute(
        select(func.count(FailurePattern.id)).where(
            FailurePattern.project_key == project_key, FailurePattern.last_status == "reappeared"
        )
    )
    reappeared = reappeared_q.scalar() or 0

    top_q = await db.execute(
        select(FailurePattern).where(FailurePattern.project_key == project_key)
        .order_by(FailurePattern.occurrence_count.desc()).limit(5)
    )
    top_patterns = [_pattern_to_dict(p) for p in top_q.scalars().all()]

    return {
        "total": total,
        "active": active,
        "resolved": resolved,
        "reappeared": reappeared,
        "top_patterns": top_patterns,
    }


def _pattern_to_dict(p: FailurePattern) -> dict:
    return {
        "id": str(p.id),
        "signature_hash": p.signature_hash,
        "error_type": p.error_type,
        "error_location": p.error_location,
        "error_exemplar": p.error_exemplar,
        "failure_modality": p.failure_modality,
        "occurrence_count": p.occurrence_count,
        "last_status": p.last_status,
        "confidence": p.confidence,
    }


def _structural_similarity(fp: dict, pattern: FailurePattern) -> float:
    score = 0.0
    if fp.get("failure_modality") == pattern.failure_modality:
        score += 0.4
    fp_loc = fp.get("error_location")
    if fp_loc and pattern.error_location:
        if fp_loc.get("file") == pattern.error_location.get("file"):
            score += 0.4
            if fp_loc.get("function") == pattern.error_location.get("function"):
                score += 0.2
    elif not fp_loc and not pattern.error_location:
        score += 0.3
    return min(score, 1.0)
