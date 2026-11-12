"""Frontend tests: every UI page is served, its scripts bind to elements that exist, and every API call the
browser code makes matches a real backend route. These catch the usual UI breakages (renamed element id,
renamed endpoint, missing asset) without needing a browser."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "web"
PAGES = sorted(p.name for p in WEB.glob("*.html"))
SCRIPTS = sorted(p.name for p in (WEB / "static").glob("*.js"))
API_CALL = re.compile(r"""\b(?:api|A)\(\s*["'](GET|POST|PUT|PATCH|DELETE)["']\s*,\s*["'`]([^"'`$]+)""")
ID_REF = re.compile(r"""\$\(\s*["']#([\w-]+)["']|getElementById\(\s*["']([\w-]+)["']""")


def _routes(client):
    """(METHOD, path) for every backend endpoint, read from the app's OpenAPI schema."""
    spec = client.get("/openapi.json", headers={"X-Forwarded-Proto": "https"}).json()
    return [(m.upper(), path) for path, ops in spec["paths"].items() for m in ops]


def test_pages_and_scripts_exist():
    assert len(PAGES) == 7 and "index.html" in PAGES
    assert {"app.js", "entry.js", "exit.js", "display.js", "booking.js", "attendant.js", "admin.js"} <= set(SCRIPTS)


@pytest.mark.parametrize("page", PAGES)
def test_page_is_served_with_its_assets(client, page):
    r = client.get(f"/ui/{page}", headers={"X-Forwarded-Proto": "https"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    for ref in re.findall(r'(?:src|href)="(static/[^"]+)"', r.text):
        asset = client.get(f"/ui/{ref}", headers={"X-Forwarded-Proto": "https"})
        assert asset.status_code == 200, f"{page} links missing asset {ref}"


@pytest.mark.parametrize("page", PAGES)
def test_page_has_security_headers(client, page):
    r = client.get(f"/ui/{page}", headers={"X-Forwarded-Proto": "https"})
    csp = r.headers["content-security-policy"]
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("script", [s for s in SCRIPTS if s != "app.js"])
def test_script_element_ids_exist_in_its_page(script):
    js = (WEB / "static" / script).read_text()
    html = (WEB / script.replace(".js", ".html")).read_text()
    ids_in_page = set(re.findall(r'id="([\w-]+)"', html))
    referenced = {a or b for a, b in ID_REF.findall(js)}
    assert referenced, f"{script} references no elements"
    assert referenced <= ids_in_page, f"{script} uses ids missing from the page: {sorted(referenced - ids_in_page)}"


@pytest.mark.parametrize("script", SCRIPTS)
def test_script_api_calls_match_backend_routes(client, script):
    routes = _routes(client)
    for method, path in API_CALL.findall((WEB / "static" / script).read_text()):
        prefix = path.split("?")[0]
        assert any(m == method and (p == prefix or p.startswith(prefix)) for m, p in routes), \
            f"{script}: {method} {prefix} has no backend route"


@pytest.mark.parametrize("page", PAGES)
def test_pages_load_shared_helpers_first(page):
    scripts = re.findall(r'<script src="([^"]+)"', (WEB / page).read_text())
    assert scripts[0] == "static/app.js", f"{page} must load app.js before its page script"
