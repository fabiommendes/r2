from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from r2.web.app import Viewer
from r2.web.registry import register
from r2.web.security import TOKEN_COOKIE
from tests.reports.repo import Repo, set_mtime
from tests.web.support import BEARER, ORIGIN, TOKEN

Json = dict[str, Any]

type ClientFactory = Callable[..., TestClient]


@pytest.fixture
def make_client(repo: Repo) -> Iterator[ClientFactory]:
    """Clients over the repo's viewer. The lifespan runs between enter and exit."""
    opened: list[TestClient] = []

    def make(**options: Any) -> TestClient:
        viewer = Viewer([repo.project], TOKEN, watch=False, **options)
        client = TestClient(viewer.asgi, base_url=ORIGIN)
        client.__enter__()
        opened.append(client)
        return client

    yield make
    for client in opened:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client: ClientFactory) -> TestClient:
    return make_client()


def report_url(repo: Repo, path: str) -> str:
    return f"/api/p/{repo.project.id}/report?path={path}"


def get_report(client: TestClient, repo: Repo, path: str) -> Json:
    response = client.get(report_url(repo, path), headers=BEARER)
    assert response.status_code == 200, response.text
    body: Json = response.json()
    return body


class TestAuthentication:
    def test_refuses_the_api_without_a_token(self, client: TestClient) -> None:
        response = client.get("/api/health")
        assert response.status_code == 401
        assert response.text == "unauthorized\n"

    def test_refuses_a_wrong_token(self, client: TestClient) -> None:
        response = client.get("/api/health", headers={"authorization": "Bearer nope"})
        assert response.status_code == 401

    def test_accepts_a_bearer_token(self, client: TestClient) -> None:
        response = client.get("/api/health", headers=BEARER)
        assert response.status_code == 200
        assert response.json() == {"ok": True, "projects": 1}

    def test_accepts_the_cookie_the_browser_was_given(self, client: TestClient) -> None:
        response = client.get(
            "/api/health", headers={"cookie": f"{TOKEN_COOKIE}={TOKEN}"}
        )
        assert response.status_code == 200

    def test_the_cookie_is_called_r2_token(self) -> None:
        assert TOKEN_COOKIE == "r2_token"

    def test_refuses_a_cookie_with_the_wrong_token(self, client: TestClient) -> None:
        response = client.get("/api/health", headers={"cookie": f"{TOKEN_COOKIE}=nope"})
        assert response.status_code == 401

    def test_hands_out_the_cookie_at_auth_and_redirects(
        self, client: TestClient
    ) -> None:
        response = client.get(f"/auth?token={TOKEN}&to=/p/x", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/p/x"
        cookie = response.headers["set-cookie"]
        assert cookie.startswith(f"{TOKEN_COOKIE}={TOKEN}")
        assert "httponly" in cookie.lower()
        assert "samesite=strict" in cookie.lower()

    def test_the_cookie_from_auth_opens_the_api(self, client: TestClient) -> None:
        client.get(f"/auth?token={TOKEN}", follow_redirects=False)
        assert client.get("/api/health").status_code == 200

    def test_refuses_auth_with_the_wrong_token(self, client: TestClient) -> None:
        response = client.get("/auth?token=nope", follow_redirects=False)
        assert response.status_code == 401
        assert "set-cookie" not in response.headers

    @pytest.mark.parametrize(
        "target",
        ["https://evil.example", "//evil.example", "evil.example/x"],
    )
    def test_never_redirects_auth_off_site(
        self, client: TestClient, target: str
    ) -> None:
        response = client.get(
            "/auth", params={"token": TOKEN, "to": target}, follow_redirects=False
        )
        assert response.headers["location"] == "/"


class TestOriginAndHost:
    def test_refuses_a_foreign_origin(self, client: TestClient) -> None:
        response = client.get(
            "/api/health", headers={**BEARER, "origin": "https://evil.example"}
        )
        assert response.status_code == 403

    def test_accepts_its_own_origin(self, client: TestClient) -> None:
        response = client.get(
            "/api/health", headers={**BEARER, "origin": "http://localhost:7718"}
        )
        assert response.status_code == 200

    def test_refuses_a_rebound_host(self, client: TestClient) -> None:
        response = client.get(
            "/api/health", headers={**BEARER, "host": "evil.example:7717"}
        )
        assert response.status_code == 403

    def test_accepts_an_ipv6_loopback_host(self, client: TestClient) -> None:
        response = client.get("/api/health", headers={**BEARER, "host": "[::1]:7717"})
        assert response.status_code == 200

    def test_the_guard_covers_the_auth_route_too(self, client: TestClient) -> None:
        response = client.get(
            f"/auth?token={TOKEN}",
            headers={"origin": "https://evil.example"},
            follow_redirects=False,
        )
        assert response.status_code == 403

    def test_answers_for_the_hostnames_it_was_given(
        self, make_client: ClientFactory
    ) -> None:
        client = make_client(hostnames=["reports.local"])
        accepted = client.get(
            "/api/health", headers={**BEARER, "host": "reports.local"}
        )
        refused = client.get("/api/health", headers={**BEARER, "host": "localhost"})
        assert (accepted.status_code, refused.status_code) == (200, 403)

    def test_sets_defensive_headers(self, client: TestClient) -> None:
        headers = client.get("/api/health", headers=BEARER).headers
        assert headers["x-frame-options"] == "DENY"
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "no-referrer"


class TestProjectsAndReports:
    def test_lists_projects(self, client: TestClient, repo: Repo) -> None:
        body = client.get("/api/projects", headers=BEARER).json()
        assert body == [{"id": repo.project.id, "name": "repo", "root": str(repo.root)}]

    def test_lists_reports_newest_first(self, client: TestClient, repo: Repo) -> None:
        set_mtime(repo.write_report("old", "# Old\n"), 1_000_000)
        set_mtime(repo.write_report("deep/new", "# New\n"), 1_000_100)
        response = client.get(f"/api/p/{repo.project.id}/reports", headers=BEARER)
        body = response.json()
        assert [r["path"] for r in body] == ["deep/new", "old"]
        assert isinstance(body[0]["modified"], str)

    def test_a_summary_omits_absent_fields_instead_of_sending_null(
        self, client: TestClient, repo: Repo
    ) -> None:
        repo.write_report("plain", "# Plain\n")
        body = client.get(f"/api/p/{repo.project.id}/reports", headers=BEARER).json()
        assert "severity" not in body[0]
        assert "read" not in body[0]
        assert body[0]["open"] is False

    def test_returns_a_rendered_document(self, client: TestClient, repo: Repo) -> None:
        repo.write_report(
            "auth",
            "---\ntitle: Auth flow\nkind: review\n---\n\n"
            "```rl:finding severity=high ref=src/a.ts:4-8\n"
            "Token is not rotated.\n```\n",
        )
        body = get_report(client, repo, "auth")
        assert body["title"] == "Auth flow"
        assert body["rendered"]["findings"][0]["severity"] == "high"
        assert body["rendered"]["refs"][0]["path"] == "src/a.ts"

    def test_a_document_without_marks_has_no_marks_field(
        self, client: TestClient, repo: Repo
    ) -> None:
        repo.write_report("auth", "# Auth\n")
        assert "marks" not in get_report(client, repo, "auth")

    def test_serves_a_nested_report_path(self, client: TestClient, repo: Repo) -> None:
        repo.write_report("group/inner", "# Inner\n")
        assert get_report(client, repo, "group/inner")["path"] == "group/inner"

    def test_404s_an_unknown_report_and_an_unknown_project(
        self, client: TestClient, repo: Repo
    ) -> None:
        missing = client.get(report_url(repo, "nope"), headers=BEARER)
        assert (missing.status_code, missing.text) == (404, "no such report\n")
        unknown = client.get("/api/p/nope/reports", headers=BEARER)
        assert (unknown.status_code, unknown.text) == (404, "no such project\n")

    def test_refuses_a_report_path_that_climbs_out(
        self, client: TestClient, repo: Repo
    ) -> None:
        response = client.get(
            report_url(repo, "..%2F..%2Fetc%2Fpasswd"), headers=BEARER
        )
        assert (response.status_code, response.text) == (400, "bad report path\n")

    def test_the_report_routes_need_the_token(
        self, client: TestClient, repo: Repo
    ) -> None:
        repo.write_report("auth", "# Auth\n")
        assert client.get(report_url(repo, "auth")).status_code == 401
        assert client.get(f"/api/p/{repo.project.id}/reports").status_code == 401


class TestResolvingReferences:
    def test_resolves_a_ref_and_a_candidate_that_exist_and_nothing_else(
        self, client: TestClient, repo: Repo
    ) -> None:
        report = repo.write_report(
            "auth",
            "Broken in src/a.ts:1 and also in src/gone.ts somewhere.\n\n"
            "```rl:finding severity=low ref=src/a.ts:1\nMinor.\n```\n",
        )
        set_mtime(report, 2_000_000)
        set_mtime(repo.write_file("src/a.ts", "const a = 1\n"), 1_000_000)
        resolutions = get_report(client, repo, "auth")["resolutions"]
        assert list(resolutions) == ["src/a.ts"]
        assert "changed" not in resolutions["src/a.ts"]
        assert isinstance(resolutions["src/a.ts"]["modified"], str)

    def test_says_when_a_cited_file_changed_after_the_report(
        self, client: TestClient, repo: Repo
    ) -> None:
        set_mtime(repo.write_report("auth", "See src/a.ts for the rest.\n"), 1_000_000)
        set_mtime(repo.write_file("src/a.ts", "const a = 1\n"), 2_000_000)
        resolutions = get_report(client, repo, "auth")["resolutions"]
        assert resolutions["src/a.ts"]["changed"] is True

    def test_resolves_nothing_for_a_report_with_no_references(
        self, client: TestClient, repo: Repo
    ) -> None:
        repo.write_report("plain", "# Nothing to see\n")
        assert get_report(client, repo, "plain")["resolutions"] == {}

    def test_a_cited_symlink_that_leaves_the_project_is_not_resolved(
        self, client: TestClient, repo: Repo, tmp_path: Path
    ) -> None:
        secret = tmp_path / "secret.txt"
        secret.write_text("secret\n")
        (repo.root / "leak.txt").symlink_to(secret)
        repo.write_report("auth", "See leak.txt please.\n")
        assert get_report(client, repo, "auth")["resolutions"] == {}


class TestFileListing:
    def test_lists_project_files(self, client: TestClient, repo: Repo) -> None:
        repo.write_file("src/a.ts", "const a = 1\n")
        repo.write_file("README.md", "# Readme\n")
        response = client.get(f"/api/p/{repo.project.id}/files", headers=BEARER)
        assert response.status_code == 200
        body = response.json()
        assert [f["path"] for f in body] == ["README.md", "src/a.ts"]
        assert isinstance(body[0]["modified"], str)
        assert body[0]["size"] == 9


class TestFileContents:
    @pytest.fixture
    def fetch(self, client: TestClient, repo: Repo) -> Callable[..., Any]:
        def fetch(path: str, **options: Any) -> Any:
            return client.get(
                f"/api/p/{repo.project.id}/file",
                params={"path": path},
                **{"headers": BEARER, **options},
            )

        return fetch

    def test_serves_lines_and_language_without_highlighting(
        self, repo: Repo, fetch: Callable[..., Any]
    ) -> None:
        repo.write_file("src/a.ts", "const a = 1\nconst b = 2\n")
        response = fetch("src/a.ts")
        assert response.status_code == 200
        body = response.json()
        assert body["lines"] == ["const a = 1", "const b = 2"]
        assert body["lang"] == "typescript"
        assert body["path"] == "src/a.ts"
        assert "highlight" not in body

    def test_serves_a_file_with_no_grammar_without_a_language(
        self, repo: Repo, fetch: Callable[..., Any]
    ) -> None:
        repo.write_file("notes.unknownext", "plain text\n")
        body = fetch("notes.unknownext").json()
        assert body["lines"] == ["plain text"]
        assert "lang" not in body
        assert "truncated" not in body

    def test_404s_a_file_that_is_not_there(self, fetch: Callable[..., Any]) -> None:
        response = fetch("src/nope.ts")
        assert (response.status_code, response.text) == (404, "no such file\n")

    def test_400s_a_path_that_climbs_out_or_is_empty(
        self, fetch: Callable[..., Any]
    ) -> None:
        assert fetch("../../etc/passwd").status_code == 400
        assert fetch("/etc/passwd").status_code == 400
        assert fetch("").status_code == 400

    def test_415s_a_binary_file(self, repo: Repo, fetch: Callable[..., Any]) -> None:
        repo.write_file("logo.png", bytes([0x89, 0x50, 0x4E, 0x47, 0x00, 0x01]))
        assert fetch("logo.png").status_code == 415

    def test_does_not_serve_a_symlink_that_leaves_the_project(
        self, repo: Repo, fetch: Callable[..., Any], tmp_path: Path
    ) -> None:
        secret = tmp_path / "secret.txt"
        secret.write_text("secret\n")
        (repo.root / "leak.txt").symlink_to(secret)
        response = fetch("leak.txt")
        assert response.status_code == 404
        assert "secret" not in response.text

    def test_needs_the_token(self, repo: Repo, fetch: Callable[..., Any]) -> None:
        repo.write_file("src/a.ts", "x\n")
        assert fetch("src/a.ts", headers={}).status_code == 401


class TestFileLinks:
    """What the file view adds on top of the lines: Markdown and path links."""

    @pytest.fixture
    def fetch(self, client: TestClient, repo: Repo) -> Callable[[str], Json]:
        def fetch(path: str) -> Json:
            response = client.get(
                f"/api/p/{repo.project.id}/file",
                params={"path": path},
                headers=BEARER,
            )
            assert response.status_code == 200, response.text
            body: Json = response.json()
            return body

        return fetch

    def test_a_markdown_file_gets_a_rendered_document(
        self, repo: Repo, fetch: Callable[[str], Json]
    ) -> None:
        repo.write_file("docs/guide.md", "# Guide\n\nSome text.\n")
        body = fetch("docs/guide.md")
        assert body["rendered"]["firstHeading"] == "Guide"
        assert [node["type"] for node in body["rendered"]["nodes"]] == [
            "heading",
            "paragraph",
        ]

    def test_a_readme_without_extension_is_markdown_too(
        self, repo: Repo, fetch: Callable[[str], Json]
    ) -> None:
        repo.write_file("README", "# Title\n")
        assert fetch("README")["rendered"]["firstHeading"] == "Title"

    def test_a_code_file_has_no_rendered_document(
        self, repo: Repo, fetch: Callable[[str], Json]
    ) -> None:
        repo.write_file("src/a.py", "x = 1\n")
        assert "rendered" not in fetch("src/a.py")

    def test_a_markdown_file_resolves_the_paths_it_cites(
        self, repo: Repo, fetch: Callable[[str], Json]
    ) -> None:
        repo.write_file("src/a.py", "x = 1\n")
        repo.write_file("docs/guide.md", "See src/a.py and src/gone.py.\n")
        assert list(fetch("docs/guide.md")["resolutions"]) == ["src/a.py"]

    def test_a_line_citing_an_existing_path_gets_a_link_and_a_resolution(
        self, repo: Repo, fetch: Callable[[str], Json]
    ) -> None:
        repo.write_file("src/a.py", "x = 1\n")
        repo.write_file("notes.py", "# first\n# see src/a.py here\n")
        body = fetch("notes.py")
        assert len(body["links"]) == 1
        link = body["links"][0]
        assert (link["line"], link["start"], link["end"]) == (2, 6, 14)
        assert link["candidate"]["path"] == "src/a.py"
        assert list(body["resolutions"]) == ["src/a.py"]
        assert body["resolutions"]["src/a.py"]["path"] == "src/a.py"

    def test_link_offsets_count_utf16_code_units(
        self, repo: Repo, fetch: Callable[[str], Json]
    ) -> None:
        repo.write_file("src/a.py", "x = 1\n")
        # The emoji is one code point and two UTF-16 code units, so the path
        # starts at 9 for a JavaScript string and at 8 for a Python one.
        repo.write_file("notes.py", "# \N{GRINNING FACE} see src/a.py\n")
        link = fetch("notes.py")["links"][0]
        assert (link["line"], link["start"], link["end"]) == (1, 9, 17)

    def test_a_path_that_does_not_exist_gets_no_link_and_no_resolution(
        self, repo: Repo, fetch: Callable[[str], Json]
    ) -> None:
        repo.write_file("notes.py", "# see src/gone.py here\n")
        body = fetch("notes.py")
        assert body["links"] == []
        assert body["resolutions"] == {}

    def test_a_file_that_cites_nothing_has_empty_links_and_resolutions(
        self, repo: Repo, fetch: Callable[[str], Json]
    ) -> None:
        repo.write_file("a.py", "x = 1\n")
        body = fetch("a.py")
        assert (body["links"], body["resolutions"]) == ([], {})

    def test_several_paths_on_one_line_each_get_a_link(
        self, repo: Repo, fetch: Callable[[str], Json]
    ) -> None:
        repo.write_file("src/a.py", "x = 1\n")
        repo.write_file("src/b.py", "y = 2\n")
        repo.write_file("notes.py", "# src/a.py then src/b.py\n")
        links = fetch("notes.py")["links"]
        assert [(link["start"], link["end"]) for link in links] == [(2, 10), (16, 24)]


class TestReviewMarks:
    def put(self, client: TestClient, repo: Repo, path: str, **options: Any) -> Any:
        return client.put(
            f"/api/p/{repo.project.id}/marks",
            params={"path": path},
            headers=BEARER,
            **options,
        )

    def test_writes_and_normalizes_marks(self, client: TestClient, repo: Repo) -> None:
        repo.write_report("auth", "# Auth\n")
        response = self.put(
            client,
            repo,
            "auth",
            json={
                "read": "2026-09-30T15:00:00Z",
                "findings": {"f1": {"state": "accepted"}, "f2": {"state": "wat"}},
            },
        )
        assert response.status_code == 200
        assert list(response.json()["findings"]) == ["f1"]
        document = get_report(client, repo, "auth")
        assert document["marks"]["read"] == "2026-09-30T15:00:00Z"
        assert document["marks"]["findings"] == {"f1": {"state": "accepted"}}

    def test_refuses_marks_for_a_report_that_does_not_exist(
        self, client: TestClient, repo: Repo
    ) -> None:
        response = self.put(client, repo, "nope", json={})
        assert response.status_code == 404

    def test_refuses_a_body_that_is_not_json(
        self, client: TestClient, repo: Repo
    ) -> None:
        repo.write_report("auth", "# Auth\n")
        response = self.put(
            client,
            repo,
            "auth",
            content="not json",
        )
        assert response.status_code == 400

    def test_refuses_a_path_that_climbs_out(
        self, client: TestClient, repo: Repo
    ) -> None:
        assert self.put(client, repo, "../x", json={}).status_code == 400

    def test_needs_the_token(self, client: TestClient, repo: Repo) -> None:
        repo.write_report("auth", "# Auth\n")
        response = client.put(
            f"/api/p/{repo.project.id}/marks", params={"path": "auth"}, json={}
        )
        assert response.status_code == 401
        assert not (repo.project.reports / "auth.review.json").exists()


class TestReload:
    def test_picks_up_a_project_registered_after_start(
        self, client: TestClient, make_repo: Callable[[str], Repo]
    ) -> None:
        other = make_repo("other")
        register(other.project)
        response = client.post("/api/reload", headers=BEARER)
        assert response.json() == {"projects": 1}
        names = [p["name"] for p in client.get("/api/projects", headers=BEARER).json()]
        assert names == ["other"]

    def test_needs_the_token(self, client: TestClient) -> None:
        assert client.post("/api/reload").status_code == 401


class TestStaticAssets:
    @pytest.fixture
    def site(self, tmp_path: Path) -> Path:
        site = tmp_path / "site"
        (site / "assets").mkdir(parents=True)
        (site / "index.html").write_text("<!doctype html><title>shell</title>")
        (site / "assets" / "app.js").write_text("console.log(1)")
        return site

    def test_falls_back_to_index_html_so_client_routes_work(
        self, make_client: ClientFactory, site: Path
    ) -> None:
        client = make_client(static_root=site)
        shell = client.get("/p/x/r/y")
        assert shell.status_code == 200
        assert "text/html" in shell.headers["content-type"]
        assert shell.headers["cache-control"] == "no-store"
        assert "shell" in shell.text

    def test_serves_assets_as_immutable(
        self, make_client: ClientFactory, site: Path
    ) -> None:
        asset = make_client(static_root=site).get("/assets/app.js")
        assert "javascript" in asset.headers["content-type"]
        assert "immutable" in asset.headers["cache-control"]
        assert asset.text == "console.log(1)"

    @pytest.mark.parametrize(
        "path",
        ["/../../etc/passwd", "/%2e%2e/%2e%2e/etc/passwd", "/..%2f..%2fetc/hosts"],
    )
    def test_never_serves_a_file_outside_the_root(
        self, make_client: ClientFactory, site: Path, path: str
    ) -> None:
        response = make_client(static_root=site).get(path)
        assert "shell" in response.text
        assert "root:" not in response.text

    def test_the_shell_needs_no_token(
        self, make_client: ClientFactory, site: Path
    ) -> None:
        assert make_client(static_root=site).get("/").status_code == 200

    def test_the_api_still_wins_over_the_shell(
        self, make_client: ClientFactory, site: Path
    ) -> None:
        client = make_client(static_root=site)
        assert client.get("/api/health").status_code == 401
        assert client.get("/api/health", headers=BEARER).status_code == 200

    def test_serves_the_api_without_a_static_root(self, client: TestClient) -> None:
        assert client.get("/p/x").status_code == 404
