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

    @property
    def projects_dir(self) -> Path:
        return Path(self.data_dir) / "projects"

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
        return self.project_dir(project_key) / "history.jsonl"

    model_config = {"env_prefix": "ALLURE_"}


settings = Settings()
