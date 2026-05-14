import asyncio
import json
import logging
from pathlib import Path
from app.config import settings

logger = logging.getLogger(__name__)


async def generate_allure_config(project_key: str, project_name: str) -> Path:
    """Generate allurerc.mjs config file for a project."""
    config_path = settings.allure_config_path(project_key)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config_content = f"""\
export default {{
  name: "{project_name}",
  historyPath: "{settings.history_path(project_key)}",
  appendHistory: true,
  plugins: {{
    awesome: {{
      options: {{
        singleFile: false,
        reportLanguage: "{settings.report_language}",
        groupBy: [
          ["epic", "feature", "story"],
          ["parentSuite", "suite", "subSuite"],
          ["package", "class", "method"],
        ],
      }}
    }}
  }}
}};
"""
    config_path.write_text(config_content)
    return config_path


async def generate_report(project_key: str, run_id: str, project_name: str) -> str:
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

    await generate_allure_config(project_key, project_name)

    cmd = [
        "npx", "allure", "awesome",
        str(results_dir),
        "-o", str(report_dir),
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

    await fix_history_urls(project_key, run_id)

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


async def fix_history_urls(project_key: str, run_id: str) -> None:
    """After a report is generated, fix the url field in history.jsonl entries
    so that Allure's History tab can link to previous reports."""
    history_path = settings.history_path(project_key)
    if not history_path.exists():
        return

    # Read all history lines
    lines = history_path.read_text().strip().splitlines()
    if not lines:
        return

    # Build entries list
    entries: list[dict] = []
    for line in lines:
        if line.strip():
            entries.append(json.loads(line))

    # Find our run's entry (last one appended by allure)
    if entries:
        latest = entries[-1]
        allure_uuid = latest.get("uuid", "")
        if allure_uuid:
            url_map = _load_url_map(project_key)
            url_map[allure_uuid] = run_id
            _save_url_map(project_key, url_map)

    # Re-read map and fix all known entries
    url_map = _load_url_map(project_key)
    changed = False
    for entry in entries:
        entry_uuid = entry.get("uuid", "")
        if entry_uuid in url_map and not entry.get("url"):
            entry["url"] = f"/reports/{project_key}/{url_map[entry_uuid]}/"
            changed = True

    if changed:
        history_path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        logger.info("Fixed history urls for project %s, run %s", project_key, run_id)
