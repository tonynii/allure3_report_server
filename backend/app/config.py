from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://allure:allure@localhost:5432/allure3"
    database_url_sync: str = "postgresql://allure:allure@localhost:5432/allure3"
    data_dir: str = "/data/allure"
    max_runs_default: int = 20
    report_language: str = "zh"
    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str = ""

    def build_url(self, path: str) -> str:
        """Return a full URL if base_url is set, otherwise return the relative path."""
        if not self.base_url:
            return path
        base = self.base_url.rstrip("/")
        return f"{base}{path}"

    @property
    def projects_dir(self) -> Path:
        return Path(self.data_dir) / "projects"
    
    @property
    def history_file(self) -> Path:
        return Path("history.jsonl")

    def project_dir(self, project_key: str) -> Path:
        return self.projects_dir / project_key

    def runs_dir(self, project_key: str) -> Path:
        return self.project_dir(project_key) / "runs"

    def run_dir(self, project_key: str, run_id: str) -> Path:
        return self.runs_dir(project_key) / str(run_id)

    def results_dir(self, project_key: str, run_id: str) -> Path:
        return self.run_dir(project_key, run_id) / "allure-results"

    def report_dir(self, project_key: str, run_id: str) -> Path:
        return self.run_dir(project_key, run_id) / "allure-report"

    def allure_config_path(self, project_key: str) -> Path:
        return self.project_dir(project_key) / "allurerc.mjs"

    def history_path(self, project_key: str) -> Path:
        return self.project_dir(project_key) / self.history_file

    model_config = {"env_prefix": "ALLURE_"}


settings = Settings()
