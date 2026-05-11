import asyncio
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
        reportLanguage: "en",
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

    return str(report_dir)
