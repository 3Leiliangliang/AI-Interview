from __future__ import annotations

import json
import locale
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
LOCAL_E2E_SCRIPT = ROOT_DIR / "test" / "run_local_interview_e2e.py"
FRONTEND_E2E_SCRIPT = ROOT_DIR / "test" / "e2e_frontend_verification.js"
FRONTEND_ARTIFACTS_DIR = ROOT_DIR / "test" / "artifacts"
WORKFLOW_MANIFEST_NAME = "workflow_manifest.json"
PREFERRED_ENCODING = locale.getpreferredencoding(False) or "utf-8"
EXPECTED_RUN_ROOT = (ROOT_DIR / "output" / "e2e_interview_runs").resolve()


def _resolve_if_exists(path: Path) -> str | None:
    return str(path.resolve()) if path.exists() else None


def _sorted_resolved(paths: list[Path]) -> list[str]:
    return [str(path.resolve()) for path in sorted(paths)]


def parse_backend_output(stdout: str) -> dict[str, str]:
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("output_dir") and payload.get("report"):
            output_dir = str(payload["output_dir"]).strip()
            report = str(payload["report"]).strip()
            if output_dir and report:
                return {
                    "output_dir": output_dir,
                    "report": report,
                }
    raise ValueError("未在后端 E2E 输出中找到包含 output_dir/report 的 JSON 结果")


def ensure_path_within_root(path: Path, root: Path, *, label: str) -> Path:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if not resolved_path.is_relative_to(resolved_root):
        raise ValueError(f"{label} 超出允许目录范围：{resolved_path}")
    return resolved_path


def collect_run_artifacts(run_dir: Path) -> dict[str, Any]:
    run_dir = ensure_path_within_root(run_dir, EXPECTED_RUN_ROOT, label="run_dir")
    return {
        "report_path": _resolve_if_exists(run_dir / "report.md"),
        "raw_results_path": _resolve_if_exists(run_dir / "raw_results.json"),
        "api_log_path": _resolve_if_exists(run_dir / "api.log"),
        "html_artifacts": _sorted_resolved(list(run_dir.glob("*.html"))),
        "png_artifacts": _sorted_resolved(list(run_dir.glob("*.png"))),
        "json_artifacts": _sorted_resolved(
            [path for path in run_dir.glob("*.json") if path.name != WORKFLOW_MANIFEST_NAME]
        ),
        "markdown_artifacts": _sorted_resolved([path for path in run_dir.glob("*.md") if path.name != "report.md"]),
    }


def snapshot_directory(directory: Path) -> dict[str, int]:
    if not directory.exists():
        return {}
    return {str(path.resolve()): path.stat().st_mtime_ns for path in directory.rglob("*") if path.is_file()}


def collect_new_or_changed_files(directory: Path, previous_snapshot: dict[str, int]) -> list[str]:
    current_snapshot = snapshot_directory(directory)
    changed = [path for path, mtime_ns in current_snapshot.items() if previous_snapshot.get(path) != mtime_ns]
    return sorted(changed)


def run_backend_e2e() -> dict[str, Any]:
    command = ["uv", "run", "python", str(LOCAL_E2E_SCRIPT)]
    completed = subprocess.run(
        command,
        cwd=str(ROOT_DIR),
        text=True,
        encoding=PREFERRED_ENCODING,
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"后端 E2E 执行失败\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")

    payload = parse_backend_output(completed.stdout)
    run_dir = ensure_path_within_root(Path(payload["output_dir"]), EXPECTED_RUN_ROOT, label="run_dir")
    report_path = ensure_path_within_root(Path(payload["report"]), run_dir, label="report")
    if not run_dir.exists():
        raise RuntimeError(f"后端 E2E 输出目录不存在：{run_dir}")
    if not report_path.exists():
        raise RuntimeError(f"后端 E2E 报告不存在：{report_path}")

    return {
        "status": "passed",
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "run_dir": str(run_dir),
        "report_path": str(report_path),
    }


def run_frontend_verification() -> dict[str, Any]:
    if not FRONTEND_E2E_SCRIPT.exists():
        return {
            "status": "skipped",
            "reason": f"未找到前端验证脚本：{FRONTEND_E2E_SCRIPT}",
            "artifacts": [],
        }

    before_snapshot = snapshot_directory(FRONTEND_ARTIFACTS_DIR)
    command = ["node", str(FRONTEND_E2E_SCRIPT)]
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            text=True,
            encoding=PREFERRED_ENCODING,
            errors="replace",
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        return {
            "status": "failed",
            "reason": str(exc),
            "command": command,
            "artifacts": [],
            "stdout": "",
            "stderr": "",
            "returncode": None,
        }

    artifacts = collect_new_or_changed_files(FRONTEND_ARTIFACTS_DIR, before_snapshot)
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "artifacts": artifacts,
    }


def build_workflow_manifest(
    *,
    backend_result: dict[str, Any],
    run_artifacts: dict[str, Any],
    frontend_result: dict[str, Any],
) -> dict[str, Any]:
    warnings: list[str] = []
    frontend_status = frontend_result.get("status")
    if frontend_status == "failed":
        warnings.append("前端验证脚本执行失败，已保留后端 E2E 结果")
    elif frontend_status == "skipped":
        warnings.append("前端验证步骤已跳过")

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not warnings else "passed_with_warnings",
        "run_dir": backend_result["run_dir"],
        "report_path": run_artifacts["report_path"],
        "raw_results_path": run_artifacts["raw_results_path"],
        "api_log_path": run_artifacts["api_log_path"],
        "html_artifacts": run_artifacts["html_artifacts"],
        "png_artifacts": run_artifacts["png_artifacts"],
        "json_artifacts": run_artifacts["json_artifacts"],
        "markdown_artifacts": run_artifacts["markdown_artifacts"],
        "frontend_verification": frontend_result,
        "frontend_verification_artifacts": list(frontend_result.get("artifacts") or []),
        "capture_artifacts": [],
        "backend_command": backend_result.get("command") or [],
        "warnings": warnings,
    }


def write_workflow_manifest(run_dir: Path, manifest: dict[str, Any]) -> Path:
    run_dir = ensure_path_within_root(run_dir, EXPECTED_RUN_ROOT, label="run_dir")
    manifest_path = run_dir / WORKFLOW_MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def run_workflow() -> dict[str, str]:
    backend_result = run_backend_e2e()
    run_dir = Path(backend_result["run_dir"])
    run_artifacts = collect_run_artifacts(run_dir)
    frontend_result = run_frontend_verification()
    manifest = build_workflow_manifest(
        backend_result=backend_result,
        run_artifacts=run_artifacts,
        frontend_result=frontend_result,
    )
    manifest_path = write_workflow_manifest(run_dir, manifest)
    return {
        "run_dir": str(run_dir.resolve()),
        "manifest": str(manifest_path.resolve()),
        "status": manifest["status"],
    }


def main() -> int:
    try:
        result = run_workflow()
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[workflow] 执行失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
