"""Browser end-to-end flow. Run with: pytest -m e2e (requires `playwright install chromium`)."""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e
ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def live_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    port = _free_port()
    env = {
        **os.environ,
        "APP_ENV": "development",
        "APP_INSTANCE_PATH": str(tmp_path_factory.mktemp("instance")),
        "SECRET_KEY": "e2e-secret",
        "FLASK_DEBUG": "0",
    }
    flask = [sys.executable, "-m", "flask", "--app", "wsgi"]
    subprocess.run([*flask, "db", "upgrade"], cwd=ROOT, env=env, check=True)
    proc = subprocess.Popen(
        [*flask, "run", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"{url}/api/v1/health", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        else:
            pytest.fail("server did not start")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_full_analysis_flow(live_server: str, page: Page, tmp_path: Path) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(live_server)
    page.locator("#samples .list-group-item", has_text="Employees").get_by_role(
        "button", name="Load"
    ).click()
    expect(page).to_have_url(re.compile(r"/datasets/[0-9a-f-]{36}$"))
    dataset_url = page.url
    expect(page.locator("#metric-cards")).to_contain_text("1,045")

    page.goto(f"{dataset_url}/explore")
    page.locator("[data-bs-target='#filter-body']").click()
    page.locator("#filter-add").click()
    row = page.locator(".filter-row").first
    row.get_by_label("Column").select_option("department")
    row.get_by_label("Operator").select_option("eq")
    row.get_by_label("Value").fill("Engineering")
    page.locator("#filter-apply").click()
    expect(page.locator("#filter-match")).to_contain_text("140")
    expect(page.locator("table tbody tr").first).to_contain_text("Engineering")

    page.goto(f"{dataset_url}/statistics")
    expect(page.locator("#filter-match")).to_contain_text("140")
    expect(page.locator("main")).to_contain_text("salary")

    page.goto(f"{dataset_url}/quality")
    expect(page.locator("main")).to_contain_text("Missing")

    page.goto(f"{dataset_url}/visualize")
    page.locator("#chart-type").select_option("scatter")
    expect(page.locator("#chart .main-svg").first).to_be_visible()
    expect(page.locator("#chart-meta")).to_contain_text("rows used")
    with page.expect_download() as png:
        page.locator("#chart-download").click()
    assert png.value.suggested_filename.endswith(".png")

    page.get_by_role("button", name="Export").click()
    with page.expect_download() as csv_download:
        page.locator("[data-export=statistics]").click()
    assert csv_download.value.suggested_filename == "employees-statistics-summary.csv"

    sample = tmp_path / "tiny.csv"
    sample.write_text("a,b\n1,x\n2,y\n3,\n")
    page.goto(live_server)
    page.locator("#file-input").set_input_files(str(sample))
    page.locator("#upload-button").click()
    expect(page).to_have_url(re.compile(r"/datasets/[0-9a-f-]{36}$"))
    expect(page.locator("#metric-cards")).to_contain_text("3")
    assert errors == []
