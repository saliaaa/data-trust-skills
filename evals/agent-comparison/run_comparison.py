"""Probe agent CLIs and, when one is logged in, compare with and without skills.

Without credentials this writes a pending result and does not invent scores.
Pass ``--run`` to attempt the case prompts. A client that is not logged in is
recorded as ``not run (no credentials)``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPARISON = Path(__file__).resolve().parent
CASES_PATH = COMPARISON / "cases.json"

PROMPT = (
    "Revenue on this dashboard looks too high. Check the model in "
    "examples/broken-revenue-demo. Do not edit files."
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="With-skill vs without-skill harness.")
    parser.add_argument("--run", action="store_true", help="Attempt case prompts. Still skips a client that is not logged in.")
    parser.add_argument("--runs", type=int, default=1, help="Repeats per case per condition when a client is logged in.")
    parser.add_argument("--output", type=Path, help="Where to write the JSON result.")
    parser.add_argument("--transcript-dir", type=Path, help="Where to write raw probe transcripts.")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args(argv)
    if args.runs < 1:
        print("runs must be at least 1", file=sys.stderr)
        return 2
    result = build_report(run_prompts=args.run, runs=args.runs, timeout=args.timeout, transcript_dir=args.transcript_dir)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    sys.stdout.write(text)
    return 0


def build_report(run_prompts: bool, runs: int, timeout: int, transcript_dir: Path | None) -> dict:
    cases = json.loads(CASES_PATH.read_text())
    clients = [_probe_client(spec, run_prompts, timeout, transcript_dir) for spec in CLIENT_SPECS]
    completed = []
    for client in clients:
        if client["skill_trigger"] != "attempted":
            continue
        for case in cases:
            for condition in ("with-skills", "without-skills"):
                for index in range(1, runs + 1):
                    completed.append(_run_case(client, case, condition, index, timeout, transcript_dir))
    authenticated = [item for item in clients if item["authenticated"]]
    if completed:
        status = "completed"
        reason = None
    elif any(item["installed"] and not item["authenticated"] for item in clients):
        status = "pending"
        reason = "no credentials"
    elif not any(item["installed"] for item in clients):
        status = "pending"
        reason = "no agent CLI installed"
    else:
        status = "pending"
        reason = "no authenticated client"
    return {
        "status": status,
        "reason": reason,
        "date": date.today().isoformat(),
        "model": None,
        "run_count": len(completed),
        "runs_requested_per_case": runs if authenticated and run_prompts else 0,
        "cases": [case["id"] for case in cases],
        "clients": clients,
        "results": completed,
    }


def _probe_client(spec: dict, run_prompts: bool, timeout: int, transcript_dir: Path | None) -> dict:
    binary = shutil.which(spec["binary"])
    record = {
        "id": spec["id"],
        "display": spec["display"],
        "binary": spec["binary"],
        "installed": binary is not None,
        "version": None,
        "authenticated": False,
        "skill_trigger": "not run (no credentials)",
        "probe_exit_code": None,
    }
    if binary is None:
        record["skill_trigger"] = "not run (cli not installed)"
        _write_transcript(transcript_dir, spec["id"], "probe", "binary not found on PATH\n")
        return record
    version = _capture([binary, *spec["version_args"]], timeout=20)
    record["version"] = (version.stdout or version.stderr).strip().splitlines()[-1:][0] if (version.stdout or version.stderr).strip() else None
    auth = _capture([binary, *spec["auth_args"]], timeout=30)
    auth_text = _joined(auth)
    record["authenticated"] = spec["auth_ok"](auth_text, auth.returncode)
    if not record["authenticated"]:
        record["skill_trigger"] = "not run (no credentials)"
        prompt_text = ""
        if run_prompts:
            prompt = _capture(spec["prompt_command"](binary, ROOT, PROMPT), timeout=timeout, cwd=ROOT)
            record["probe_exit_code"] = prompt.returncode
            prompt_text = "\n--- prompt attempt ---\n" + _joined(prompt)
        else:
            record["probe_exit_code"] = auth.returncode
        _write_transcript(transcript_dir, spec["id"], "probe", _joined(version) + "\n--- auth ---\n" + auth_text + prompt_text)
        return record
    record["skill_trigger"] = "attempted" if run_prompts else "not attempted (pass --run)"
    record["probe_exit_code"] = auth.returncode
    _write_transcript(transcript_dir, spec["id"], "probe", _joined(version) + "\n--- auth ---\n" + auth_text)
    return record


def _run_case(client: dict, case: dict, condition: str, index: int, timeout: int, transcript_dir: Path | None) -> dict:
    from score import score_reply

    binary = shutil.which(client["binary"])
    workspace = _workspace(condition == "with-skills")
    spec = next(item for item in CLIENT_SPECS if item["id"] == client["id"])
    command = spec["prompt_command"](binary, workspace, case["prompt"])
    if condition == "with-skills" and client["id"] == "claude-code":
        command = [binary, "-p", "--permission-mode", "plan", "--plugin-dir", str(workspace), case["prompt"]]
    if condition == "without-skills" and client["id"] == "claude-code":
        command = [binary, "-p", "--permission-mode", "plan", "--bare", case["prompt"]]
    completed = _capture(command, timeout=timeout, cwd=workspace)
    text = _joined(completed)
    name = f"{client['id']}-{case['id']}-{condition}-run-{index}"
    _write_transcript(transcript_dir, client["id"], name, text)
    scored = score_reply(case, text)
    return {
        "client": client["id"],
        "version": client["version"],
        "model": None,
        "case_id": case["id"],
        "condition": condition,
        "run_index": index,
        "exit_code": completed.returncode,
        "score": scored,
    }


def _workspace(with_skills: bool) -> Path:
    dest = Path(tempfile.mkdtemp(prefix="data-trust-compare-"))
    shutil.copytree(
        ROOT,
        dest,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache", "*.duckdb"),
    )
    if not with_skills:
        shutil.rmtree(dest / "skills", ignore_errors=True)
        shutil.rmtree(dest / ".cursor", ignore_errors=True)
        shutil.rmtree(dest / ".claude-plugin", ignore_errors=True)
        shutil.rmtree(dest / ".agents", ignore_errors=True)
        return dest
    agents = dest / ".agents" / "skills"
    agents.mkdir(parents=True, exist_ok=True)
    for skill in (dest / "skills").iterdir():
        if skill.is_dir():
            os.symlink(skill.resolve(), agents / skill.name)
    return dest


def _capture(command: list[str], timeout: int, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            command,
            124,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + "\nTIMEOUT\n",
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(command, 127, stdout="", stderr=str(exc))


def _joined(completed: subprocess.CompletedProcess[str]) -> str:
    return f"exit={completed.returncode}\n--- stdout ---\n{completed.stdout}\n--- stderr ---\n{completed.stderr}\n"


def _write_transcript(directory: Path | None, client_id: str, name: str, text: str) -> None:
    if directory is None:
        return
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{client_id}-{name}.txt").write_text(text)


def _cursor_auth_ok(text: str, code: int) -> bool:
    lowered = text.lower()
    if "not logged in" in lowered or "authentication required" in lowered:
        return False
    return code == 0


def _claude_auth_ok(text: str, code: int) -> bool:
    if '"loggedIn": false' in text or '"loggedIn":false' in text or "not logged in" in text.lower():
        return False
    return code == 0 and "loggedIn" in text


def _codex_auth_ok(text: str, code: int) -> bool:
    if "not logged in" in text.lower():
        return False
    return code == 0


def _cursor_prompt(binary: str, workspace: Path, prompt: str) -> list[str]:
    return [
        binary,
        "-p",
        "--mode",
        "ask",
        "--trust",
        "--workspace",
        str(workspace),
        "--output-format",
        "text",
        prompt,
    ]


def _claude_prompt(binary: str, workspace: Path, prompt: str) -> list[str]:
    return [binary, "-p", "--permission-mode", "plan", "--plugin-dir", str(workspace), prompt]


def _codex_prompt(binary: str, workspace: Path, prompt: str) -> list[str]:
    return [binary, "exec", "-s", "read-only", "-C", str(workspace), prompt]


CLIENT_SPECS = [
    {
        "id": "cursor-agent",
        "display": "Cursor",
        "binary": "cursor-agent",
        "version_args": ["--version"],
        "auth_args": ["status"],
        "auth_ok": _cursor_auth_ok,
        "prompt_command": _cursor_prompt,
    },
    {
        "id": "claude-code",
        "display": "Claude Code",
        "binary": "claude",
        "version_args": ["--version"],
        "auth_args": ["auth", "status"],
        "auth_ok": _claude_auth_ok,
        "prompt_command": _claude_prompt,
    },
    {
        "id": "codex",
        "display": "Codex",
        "binary": "codex",
        "version_args": ["--version"],
        "auth_args": ["login", "status"],
        "auth_ok": _codex_auth_ok,
        "prompt_command": _codex_prompt,
    },
]


if __name__ == "__main__":
    raise SystemExit(main())
