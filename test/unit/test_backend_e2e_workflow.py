from __future__ import annotations

import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = PROJECT_ROOT / "test" / "run_backend_e2e_workflow.py"
SPEC = importlib.util.spec_from_file_location("backend_e2e_workflow", MODULE_PATH)
workflow = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(workflow)


def test_parse_backend_output_uses_last_valid_json_line():
    stdout = "\n".join(
        [
            "[E2E] 启动本地 API 服务",
            '{"foo": "bar"}',
            '{"output_dir": "C:/tmp/run-1", "report": "C:/tmp/run-1/report.md"}',
        ]
    )

    result = workflow.parse_backend_output(stdout)

    assert result == {
        "output_dir": "C:/tmp/run-1",
        "report": "C:/tmp/run-1/report.md",
    }


def test_parse_backend_output_requires_expected_fields():
    stdout = '[E2E] done\n{"output_dir": "C:/tmp/run-1"}'

    try:
        workflow.parse_backend_output(stdout)
    except ValueError as exc:
        assert "output_dir/report" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_ensure_path_within_root_rejects_paths_outside_root(tmp_path: Path):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside"
    outside.mkdir(parents=True, exist_ok=True)

    try:
        workflow.ensure_path_within_root(outside, allowed_root, label="run_dir")
    except ValueError as exc:
        assert "超出允许目录范围" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_write_workflow_manifest_rejects_paths_outside_root(tmp_path: Path, monkeypatch):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside"
    outside.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(workflow, "EXPECTED_RUN_ROOT", allowed_root.resolve())

    try:
        workflow.write_workflow_manifest(outside, {"status": "passed"})
    except ValueError as exc:
        assert "超出允许目录范围" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_collect_run_artifacts_returns_expected_paths(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(workflow, "EXPECTED_RUN_ROOT", tmp_path.resolve())

    (tmp_path / "report.md").write_text("# report", encoding="utf-8")
    (tmp_path / "raw_results.json").write_text("{}", encoding="utf-8")
    (tmp_path / "api.log").write_text("ok", encoding="utf-8")
    (tmp_path / "result_round_1.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "result_round_1.png").write_text("png", encoding="utf-8")
    (tmp_path / "resume.md").write_text("resume", encoding="utf-8")

    result = workflow.collect_run_artifacts(tmp_path)

    assert result["report_path"] == str((tmp_path / "report.md").resolve())
    assert result["raw_results_path"] == str((tmp_path / "raw_results.json").resolve())
    assert result["api_log_path"] == str((tmp_path / "api.log").resolve())
    assert result["html_artifacts"] == [str((tmp_path / "result_round_1.html").resolve())]
    assert result["png_artifacts"] == [str((tmp_path / "result_round_1.png").resolve())]
    assert result["markdown_artifacts"] == [str((tmp_path / "resume.md").resolve())]


def test_collect_new_or_changed_files_detects_updates(tmp_path: Path):
    target = tmp_path / "example.txt"
    before = workflow.snapshot_directory(tmp_path)
    target.write_text("updated", encoding="utf-8")

    changed = workflow.collect_new_or_changed_files(tmp_path, before)

    assert changed == [str(target.resolve())]


def test_build_workflow_manifest_marks_frontend_failures_as_warning():
    backend_result = {
        "run_dir": "C:/tmp/run-1",
        "command": ["uv", "run", "python", "test/run_local_interview_e2e.py"],
    }
    run_artifacts = {
        "report_path": "C:/tmp/run-1/report.md",
        "raw_results_path": "C:/tmp/run-1/raw_results.json",
        "api_log_path": "C:/tmp/run-1/api.log",
        "html_artifacts": ["C:/tmp/run-1/result_round_1.html"],
        "png_artifacts": ["C:/tmp/run-1/result_round_1.png"],
        "json_artifacts": ["C:/tmp/run-1/raw_results.json"],
        "markdown_artifacts": [],
    }
    frontend_result = {
        "status": "failed",
        "artifacts": ["C:/repo/test/artifacts/01_homepage.png"],
        "returncode": 1,
        "stdout": "",
        "stderr": "boom",
    }

    manifest = workflow.build_workflow_manifest(
        backend_result=backend_result,
        run_artifacts=run_artifacts,
        frontend_result=frontend_result,
    )

    assert manifest["status"] == "passed_with_warnings"
    assert manifest["frontend_verification_artifacts"] == frontend_result["artifacts"]
    assert manifest["warnings"] == ["前端验证脚本执行失败，已保留后端 E2E 结果"]


def test_run_frontend_verification_handles_missing_node(tmp_path: Path, monkeypatch):
    script_path = tmp_path / "e2e_frontend_verification.js"
    script_path.write_text("console.log('noop')", encoding="utf-8")
    artifacts_dir = tmp_path / "artifacts"

    monkeypatch.setattr(workflow, "FRONTEND_E2E_SCRIPT", script_path)
    monkeypatch.setattr(workflow, "FRONTEND_ARTIFACTS_DIR", artifacts_dir)
    monkeypatch.setattr(workflow, "snapshot_directory", lambda _directory: {})

    def raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("node not found")

    monkeypatch.setattr(workflow.subprocess, "run", raise_file_not_found)

    result = workflow.run_frontend_verification()

    assert result["status"] == "failed"
    assert result["returncode"] is None
    assert "node not found" in result["reason"]


def test_run_frontend_verification_returns_failed_result_without_raising(tmp_path: Path, monkeypatch):
    script_path = tmp_path / "e2e_frontend_verification.js"
    script_path.write_text("console.log('noop')", encoding="utf-8")
    artifacts_dir = tmp_path / "artifacts"

    monkeypatch.setattr(workflow, "FRONTEND_E2E_SCRIPT", script_path)
    monkeypatch.setattr(workflow, "FRONTEND_ARTIFACTS_DIR", artifacts_dir)
    monkeypatch.setattr(workflow, "snapshot_directory", lambda _directory: {"old.png": 1})
    monkeypatch.setattr(
        workflow,
        "collect_new_or_changed_files",
        lambda _directory, _previous_snapshot: [str((artifacts_dir / "02_login_failed.png").resolve())],
    )

    class FakeCompleted:
        returncode = 1
        stdout = "frontend failed"
        stderr = "stacktrace"

    monkeypatch.setattr(workflow.subprocess, "run", lambda *args, **kwargs: FakeCompleted())

    result = workflow.run_frontend_verification()

    assert result["status"] == "failed"
    assert result["artifacts"] == [str((artifacts_dir / "02_login_failed.png").resolve())]
    assert result["returncode"] == 1


def test_run_workflow_writes_manifest_when_frontend_fails(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(workflow, "EXPECTED_RUN_ROOT", tmp_path.resolve())
    run_dir = tmp_path / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "report.md").write_text("# report", encoding="utf-8")
    (run_dir / "raw_results.json").write_text("{}", encoding="utf-8")
    (run_dir / "api.log").write_text("ok", encoding="utf-8")

    monkeypatch.setattr(
        workflow,
        "run_backend_e2e",
        lambda: {
            "status": "passed",
            "run_dir": str(run_dir.resolve()),
            "report_path": str((run_dir / "report.md").resolve()),
            "command": ["uv", "run", "python", "test/run_local_interview_e2e.py"],
        },
    )
    monkeypatch.setattr(
        workflow,
        "run_frontend_verification",
        lambda: {
            "status": "failed",
            "artifacts": [],
            "returncode": 1,
            "stdout": "",
            "stderr": "boom",
        },
    )

    result = workflow.run_workflow()
    manifest_path = Path(result["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert result["status"] == "passed_with_warnings"
    assert manifest_path.exists()
    assert manifest["run_dir"] == str(run_dir.resolve())
    assert manifest["report_path"] == str((run_dir / "report.md").resolve())
    assert manifest["raw_results_path"] == str((run_dir / "raw_results.json").resolve())
