import asyncio
import json
import logging
from pathlib import Path
from app.config import settings

logger = logging.getLogger(__name__)

_project_locks: dict[str, asyncio.Lock] = {}


def acquire_project_lock(project_key: str) -> asyncio.Lock:
    if project_key not in _project_locks:
        _project_locks[project_key] = asyncio.Lock()
    return _project_locks[project_key]


async def generate_allure_config(project_key: str, allure_config: str | None, project_name: str) -> Path:
    """Write allurerc.mjs from DB config or default."""
    config_path = settings.allure_config_path(project_key)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    content = allure_config if allure_config else _default_allure_config_mjs(project_name)
    config_path.write_text(content)
    return config_path


def _default_allure_config_mjs(project_name: str) -> str:
    return f"""\
export default {{
  name: "{project_name}",
  historyPath: "{settings.history_file}",
  appendHistory: true,
  qualityGate: {{
    rules: [
      {{
        maxFailures: 5,
        fastFail: true,
      }},
    ],
  }},
  plugins: {{
    awesome: {{
      options: {{
        reportName: "{project_name}",
        singleFile: false,
        reportLanguage: "{settings.report_language}",
        groupBy: ["epic", "feature", "story"],
      }}
    }},
    dashboard: {{
      options: {{
        singleFile: false,
        reportName: "{project_name}-Dashboard",
        reportLanguage: "{settings.report_language}",
      }},
    }},
  }}
}};
"""


async def generate_report(project_key: str, run_id: str, project_name: str, allure_config: str | None = None) -> str:
    """
    Run allure awesome to generate a static HTML report.
    Returns the report directory path on success.
    Raises RuntimeError on failure.
    """
    results_dir = settings.results_dir(project_key, run_id)
    report_dir = settings.report_dir(project_key, run_id)
    project_dir = settings.project_dir(project_key)

    results_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    cleanup_stale_history(project_key)
    cleanup_history_for_runs(project_key, [run_id])
    pre_fill_history_urls(project_key)
    write_executor_json(project_key, run_id, results_dir)
    await generate_allure_config(project_key, allure_config, project_name)

    cmd = [
        "npx", "allure", "generate",
        str(results_dir),
        "-o", str(report_dir),
        "-c", str(settings.allure_config_path(project_key)),
    ]

    logger.info("Running from %s: %s", project_dir, " ".join(cmd))

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(project_dir),
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        error_msg = stderr.decode() if stderr else stdout.decode()
        logger.error("Allure generation failed: %s", error_msg)
        raise RuntimeError(f"Allure generation failed: {error_msg}")

    logger.info("Allure generation succeeded for run %s", run_id)
    logger.debug("stdout: %s", stdout.decode())

    register_new_run_uuid(project_key, run_id)

    return str(report_dir)


def _load_url_map(project_key: str) -> dict[str, str]:
    """Load {allure_uuid → run_id} mapping file."""
    map_path = settings.project_dir(project_key) / "url_map.json"
    if map_path.exists():
        return json.loads(map_path.read_text())
    return {}


def _save_url_map(project_key: str, data: dict[str, str]) -> None:
    map_path = settings.project_dir(project_key) / "url_map.json"
    map_path.write_text(json.dumps(data, indent=2))


def pre_fill_history_urls(project_key: str) -> None:
    """Fill known URLs in history.jsonl BEFORE allure generates the report,
    so the generated HTML includes correct history links."""
    history_path = settings.history_path(project_key)
    if not history_path.exists():
        return

    url_map = _load_url_map(project_key)
    if not url_map:
        return

    lines = history_path.read_text().strip().splitlines()
    changed = False
    entries: list[dict] = []
    for line in lines:
        if not line.strip():
            continue
        entry = json.loads(line)
        uuid = entry.get("uuid", "")
        if uuid in url_map:
            entry["url"] = settings.build_url(f"/reports/{project_key}/{url_map[uuid]}/")
            changed = True
        entries.append(entry)

    if changed:
        history_path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        logger.info("Pre-filled history urls for project %s", project_key)


def register_new_run_uuid(project_key: str, run_id: str) -> None:
    """After generation, find the new entry Allure appended to history.jsonl
    and register its uuid → run_id mapping."""
    history_path = settings.history_path(project_key)
    if not history_path.exists():
        return

    lines = history_path.read_text().strip().splitlines()
    if not lines:
        return

    latest = json.loads(lines[-1])
    allure_uuid = latest.get("uuid", "")
    if allure_uuid:
        url_map = _load_url_map(project_key)
        url_map[allure_uuid] = run_id
        _save_url_map(project_key, url_map)
        logger.info("Registered run %s uuid %s", run_id, allure_uuid)


def write_executor_json(project_key: str, run_id: str, results_dir: Path) -> None:
    """Write executor.json into allure-results for CI/executor metadata in the report."""
    executor = {
        "name": "Allure Report Service",
        "type": "allure3-s",
        "buildName": f"{project_key} #{run_id[:8]}",
        "buildUrl": settings.build_url(f"/projects/{project_key}/runs/{run_id}/"),
        "reportUrl": settings.build_url(f"/reports/{project_key}/{run_id}/"),
    }
    (results_dir / "executor.json").write_text(json.dumps(executor, indent=2))


def cleanup_history_for_runs(project_key: str, run_ids: list[str]) -> None:
    """Remove history.jsonl entries and url_map entries for deleted runs."""
    url_map = _load_url_map(project_key)
    uuids_to_remove = {uuid for uuid, rid in url_map.items() if rid in run_ids}

    if uuids_to_remove:
        for uuid in uuids_to_remove:
            del url_map[uuid]
        _save_url_map(project_key, url_map)

    if not uuids_to_remove:
        return

    history_path = settings.history_path(project_key)
    if not history_path.exists():
        return

    lines = history_path.read_text().strip().splitlines()
    new_lines = [
        line for line in lines
        if line.strip() and json.loads(line).get("uuid") not in uuids_to_remove
    ]
    if len(new_lines) != len(lines):
        history_path.write_text("\n".join(new_lines) + "\n")
        logger.info(
            "Cleaned %d history entries for project %s",
            len(lines) - len(new_lines), project_key,
        )


def cleanup_stale_history(project_key: str) -> None:
    """Remove url_map and history entries for runs whose filesystem directory
    no longer exists (e.g. deleted before history cleanup was implemented)."""
    url_map = _load_url_map(project_key)
    if not url_map:
        return

    stale_run_ids: set[str] = set()
    for run_id in url_map.values():
        run_dir = settings.run_dir(project_key, run_id)
        if not run_dir.exists():
            stale_run_ids.add(run_id)

    if stale_run_ids:
        logger.info(
            "Found %d stale history entries for project %s", len(stale_run_ids), project_key,
        )
        cleanup_history_for_runs(project_key, list(stale_run_ids))
