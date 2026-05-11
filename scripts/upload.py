#!/usr/bin/env python3
"""Upload local allure-results to Allure3 Report Service."""

import argparse
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import httpx


def format_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    else:
        return f"{n / (1024 * 1024):.1f} MB"


def count_files(d: Path) -> int:
    return sum(1 for _ in d.rglob("*") if _.is_file())


def dir_size(d: Path) -> int:
    return sum(f.stat().st_size for f in d.rglob("*") if f.is_file())


def status_icon(value: int) -> str:
    return f"\033[32m{value}\033[0m" if value == 0 else f"\033[31m{value}\033[0m"


def package_results(results_path: Path) -> tuple[Path, bool]:
    """Return (zip_path, is_temp). If already a zip, return as-is."""
    if results_path.is_file() and results_path.suffix.lower() == ".zip":
        return results_path, False

    if not results_path.is_dir():
        print(f"\033[31m✗\033[0m Not a directory or zip: {results_path}")
        sys.exit(1)

    file_count = count_files(results_path)
    size = dir_size(results_path)
    print(f"  Packaging {results_path} ({file_count} files, {format_size(size)})...", end=" ")

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in results_path.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(results_path))
    tmp.close()
    zip_path = Path(tmp.name)
    print(f"{format_size(zip_path.stat().st_size)} zip")
    return zip_path, True


def upload(
    server: str,
    project: str,
    zip_path: Path,
    branch: str | None = None,
    commit: str | None = None,
    timeout: int = 30,
) -> httpx.Response:
    url = f"{server.rstrip('/')}/api/projects/{project}/runs"
    with open(zip_path, "rb") as f:
        files = {"file": (f"{project}-allure-results.zip", f, "application/zip")}
        params = {}
        if branch:
            params["branch"] = branch
        if commit:
            params["commit_hash"] = commit
        return httpx.post(url, files=files, params=params, timeout=timeout)


def poll(
    server: str,
    project: str,
    run_id: str,
    interval: int = 2,
    timeout: int = 300,
) -> dict:
    url = f"{server.rstrip('/')}/api/projects/{project}/runs/{run_id}"
    start = time.time()
    last_status = ""
    dots = 0

    while time.time() - start < timeout:
        try:
            r = httpx.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            status_str = f"\n\033[31m✗\033[0m Failed to poll: {e}"
            print(status_str)
            return {"status": "failed", "error_message": str(e)}

        s = data.get("status")
        if s != last_status:
            last_status = s

        if s == "completed":
            report_url = f"{server.rstrip('/')}/api/projects/{project}/reports/{run_id}/"
            total = data.get("total", 0)
            passed = data.get("passed", 0)
            failed = data.get("failed", 0)
            broken = data.get("broken", 0)
            skipped = data.get("skipped", 0)
            dur = data.get("duration_ms", 0)

            print(f"\n\033[32m✓\033[0m Report completed! ({time.time() - start:.0f}s)")
            print(f"  {report_url}")
            print(f"  Tests: {status_icon(passed)} passed  {status_icon(failed)} failed  {status_icon(broken)} broken  \033[33m{skipped}\033[0m skipped  ({total} total)")
            if dur:
                if dur >= 60000:
                    dur_str = f"{dur / 60000:.1f}m"
                elif dur >= 1000:
                    dur_str = f"{dur / 1000:.1f}s"
                else:
                    dur_str = f"{dur}ms"
                print(f"  Duration: {dur_str}")
            return data

        elif s == "failed":
            error = data.get("error_message", "Unknown error")
            print(f"\n\033[31m✗\033[0m Report generation failed: {error}")
            return data

        else:
            dots = (dots + 1) % 4
            print(f"\r\033[33m⏳\033[0m Generating report{'.' * dots}{' ' * (3 - dots)} ({time.time() - start:.0f}s elapsed)", end="", flush=True)
            time.sleep(interval)

    print(f"\n\033[33m⚠\033[0m Timed out after {timeout}s")
    return {"status": "timeout"}


def main():
    parser = argparse.ArgumentParser(
        description="Upload allure-results to Allure3 Report Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  uv run scripts/upload.py --project my-app ./allure-results/
  uv run scripts/upload.py --project my-app ./allure-results/
  uv run scripts/upload.py --server https://reports.example.com --project my-app --branch main allure-results.zip
  uv run scripts/upload.py --project my-app --no-wait ./allure-results/
        """,
    )
    parser.add_argument("results", type=str, help="Path to allure-results directory or .zip file")
    parser.add_argument("--server", "-s", default="http://localhost:8000", help="Allure3 server URL (default: http://localhost:8000)")
    parser.add_argument("--project", "-p", required=True, help="Project key (e.g., 'my-app')")
    parser.add_argument("--branch", "-b", help="Branch name")
    parser.add_argument("--commit", "-c", help="Commit hash")
    parser.add_argument("--no-wait", "-n", action="store_true", help="Upload only, don't wait for generation")
    parser.add_argument("--poll-interval", type=int, default=2, help="Polling interval in seconds (default: 2)")
    parser.add_argument("--timeout", "-t", type=int, default=300, help="Max wait time in seconds (default: 300)")

    args = parser.parse_args()
    results_path = Path(args.results).resolve()

    if not results_path.exists():
        print(f"\033[31m✗\033[0m Path not found: {results_path}")
        sys.exit(1)

    # 1. Package
    zip_path, is_temp = package_results(results_path)

    try:
        # 2. Upload
        zip_size = zip_path.stat().st_size
        print(f"  Uploading {format_size(zip_size)} to project '\033[36m{args.project}\033[0m'...", end=" ", flush=True)

        try:
            resp = upload(args.server, args.project, zip_path, args.branch, args.commit, timeout=60)
        except httpx.ConnectError:
            print(f"\n\033[31m✗\033[0m Cannot connect to {args.server}")
            sys.exit(1)
        except Exception as e:
            print(f"\n\033[31m✗\033[0m Upload failed: {e}")
            sys.exit(1)

        if resp.status_code == 404:
            print(f"\n\033[31m✗\033[0m Project '{args.project}' not found. Create it first:")
            print(f"  curl -X POST {args.server.rstrip('/')}/api/projects -H 'Content-Type: application/json' -d '{{\"key\":\"{args.project}\",\"name\":\"{args.project}\"}}'")
            sys.exit(1)

        if resp.status_code not in (200, 201, 202):
            print(f"\n\033[31m✗\033[0m Upload failed: HTTP {resp.status_code}")
            try:
                print(f"  {resp.json().get('detail', resp.text)}")
            except Exception:
                print(f"  {resp.text}")
            sys.exit(1)

        data = resp.json()
        run_id = data.get("id")
        print(f"\033[32m✓\033[0m")
        print(f"  run_id: {run_id}")

        # 3. Poll (optional)
        if args.no_wait:
            status_url = f"{args.server.rstrip('/')}/api/projects/{args.project}/runs/{run_id}"
            print(f"  Status: {status_url}")
            print(f"  Report (when ready): {args.server.rstrip('/')}/api/projects/{args.project}/reports/{run_id}/")
            return

        result = poll(args.server, args.project, run_id, args.poll_interval, args.timeout)

        if result.get("status") == "failed":
            sys.exit(1)
        elif result.get("status") == "timeout":
            sys.exit(1)

    finally:
        if is_temp:
            zip_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
