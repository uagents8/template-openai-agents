#!/usr/bin/env python3
"""Weekly deploy check (#1882 Phase 2): deploys THIS repository to the uagents8 platform's own
e2e sandbox from a Code Archive, calls POST /ask, then deletes the agent - run by
`.github/workflows/deploy-check.yml` every Monday and on demand (`workflow_dispatch`).

Catches an SDK release or a dependency drift before a customer meets it, the same "quality gate"
docs/marketing/framework-e2e.md already runs by hand for the framework sample pages - this
script automates the equivalent check for the published template repository. Mirrors
template-langgraph's own scripts/deploy_check.py almost exactly - only the agent name prefix and
the /ask request/response shape differ.

STATUS (as prepared, not yet dry-run against the real API - see this template's own
OWNER-PUBLISH-TEMPLATE.md section 5): the request/response shapes below are read from the
uagents8 monorepo's backend/app/schemas.py (AppCreate's `source_type="archive"` +
`source_archive_key`, app_type, resource_size, environment; AppResponse's `id`/`status`/`url`)
and from POST /v1/apps/upload's own multipart contract (backend/app/api/v1/endpoints/apps/
crud.py). Dry-run once by hand (`workflow_dispatch`) and read the log before trusting the
weekly schedule; adjust this script if the real API disagrees with any assumption below.

Environment:
  UAGENTS8_E2E_API_TOKEN   required - Bearer token (Cabinet API Key or PAT) for the e2e sandbox account.
  UAGENTS8_API_URL         optional - default https://api.uagents8.com
  DEPLOY_CHECK_SIZE        optional - default "T" (matches uagents8.json's recommended_size)
  DEPLOY_CHECK_TIMEOUT_S   optional - default 300 (seconds to wait for Running)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_URL = os.environ.get("UAGENTS8_API_URL", "https://api.uagents8.com").rstrip("/")
TOKEN = os.environ.get("UAGENTS8_E2E_API_TOKEN")
SIZE = os.environ.get("DEPLOY_CHECK_SIZE", "T")
TIMEOUT_S = int(os.environ.get("DEPLOY_CHECK_TIMEOUT_S", "300"))
POLL_EVERY_S = 5
TERMINAL_FAILURE_PHASES = {"failed_build", "failed_deploy", "failed_health_check"}

# Must match main.py's NO_KEY_MESSAGE.format(tool_output="5 words, 25 characters") exactly -
# the same question the smoke test uses, so the two checks stay provably in sync.
EXPECTED_ANSWER = (
    "[stub: no OPENAI_API_KEY set] Your question has 5 words, 25 characters. Add OPENAI_API_KEY "
    "under Environment Variables (Sensitive on), then redeploy, for a real model instead of this stub."
)


def _request(method: str, path: str, *, body: bytes | None = None, content_type: str | None = None) -> dict:
    url = f"{API_URL}{path}"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{method} {path} -> {exc.code}: {exc.read().decode('utf-8', 'replace')}") from exc


def _build_archive() -> bytes:
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(REPO_ROOT / "main.py", "main.py")
        archive.write(REPO_ROOT / "requirements.txt", "requirements.txt")
    return buffer.getvalue()


def _upload_archive(archive_bytes: bytes) -> str:
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="template-openai-agents.zip"\r\n'
        "Content-Type: application/zip\r\n\r\n"
    ).encode()
    body += archive_bytes
    body += f"\r\n--{boundary}--\r\n".encode()
    response = _request(
        "POST", "/v1/apps/upload", body=body, content_type=f"multipart/form-data; boundary={boundary}",
    )
    return response["source_archive_key"]


def _create_app(source_archive_key: str) -> dict:
    name = f"template-openai-agents-deploy-check-{uuid.uuid4().hex[:8]}"
    payload = {
        "name": name,
        "source_type": "archive",
        "source_archive_key": source_archive_key,
        "resource_size": SIZE,
        "app_type": "continuous",
        "environment": "sandbox",
    }
    return _request(
        "POST", "/v1/apps", body=json.dumps(payload).encode("utf-8"), content_type="application/json",
    )


def _wait_for_running(app_id: str) -> dict:
    deadline = time.monotonic() + TIMEOUT_S
    while time.monotonic() < deadline:
        app = _request("GET", f"/v1/apps/{app_id}")
        status = app.get("status")
        if status == "running":
            return app
        if app.get("deploy_phase") in TERMINAL_FAILURE_PHASES or status == "crashed":
            raise RuntimeError(f"Deploy failed: status={status!r} deploy_phase={app.get('deploy_phase')!r} "
                                f"error={app.get('error_message')!r}")
        time.sleep(POLL_EVERY_S)
    raise RuntimeError(f"Timed out after {TIMEOUT_S}s waiting for Running (last seen: {app})")


def _call_ask(agent_url: str) -> None:
    payload = json.dumps({"question": "how long is this sentence"}).encode("utf-8")
    req = urllib.request.Request(
        f"{agent_url.rstrip('/')}/ask", data=payload, headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    if body.get("answer") != EXPECTED_ANSWER:
        raise RuntimeError(f"Unexpected /ask answer: {body}")


def main() -> int:
    if not TOKEN:
        print("UAGENTS8_E2E_API_TOKEN is not set - see this template's OWNER-PUBLISH-TEMPLATE.md section 5.",
              file=sys.stderr)
        return 2

    app_id = None
    try:
        print("Building and uploading the Code Archive...")
        source_archive_key = _upload_archive(_build_archive())

        print("Creating the agent...")
        app = _create_app(source_archive_key)
        app_id = app["id"]
        print(f"Agent {app_id} created, waiting for Running (up to {TIMEOUT_S}s)...")

        app = _wait_for_running(app_id)
        agent_url = app.get("url")
        if not agent_url:
            raise RuntimeError(f"Agent is Running but has no url: {app}")

        print(f"Running at {agent_url} - calling POST /ask...")
        _call_ask(agent_url)
        print("Deploy check passed.")
        return 0
    finally:
        if app_id:
            print(f"Deleting agent {app_id}...")
            try:
                _request("DELETE", f"/v1/apps/{app_id}")
            except Exception as exc:  # noqa: BLE001 - cleanup must not mask the real result
                print(f"Warning: could not delete agent {app_id}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
