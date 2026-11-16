import os
from pathlib import Path
import re
import subprocess
import sys
import time

import httpx
import pytest

pytestmark = pytest.mark.integration


def test_server_starts_and_connects_to_postgresql(database_url, tmp_path):
    log_path = tmp_path / "uvicorn.log"
    environment = dict(os.environ, DATABASE_URL=database_url, PGCONNECT_TIMEOUT="3",
                       PYTHONDONTWRITEBYTECODE="1")
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
             "--port", "0", "--no-access-log"],
            cwd=Path(__file__).resolve().parents[2], env=environment,
            stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail(f"Uvicorn exited during startup. See {log_path}")
                match = re.search(r"Uvicorn running on (http://127\.0\.0\.1:\d+)",
                                  log_path.read_text(errors="replace"))
                if match:
                    break
                time.sleep(0.05)
            else:
                pytest.fail(f"Uvicorn did not start within 20 seconds. See {log_path}")

            with httpx.Client(base_url=match.group(1), timeout=5, trust_env=False) as client:
                for endpoint in ("/health", "/health/db"):
                    response = client.get(endpoint)
                    assert response.status_code == 200, endpoint
                    assert response.json() == {"status": "ok"}
                response = client.get("/docs")
                assert response.status_code == 200 and "swagger-ui" in response.text
                response = client.get("/openapi.json")
                assert response.status_code == 200
                assert "/health/db" in response.json()["paths"]
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
