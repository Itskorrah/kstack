"""Read-only GitHub discovery; does not fetch or run arbitrary URLs."""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .security import valid_repo, valid_path, SHA

class GitHubError(RuntimeError):
    pass


class GitHubAPI:
    def __init__(self, token: str | None = None, transport=None):
        self.token = token if token is not None else os.environ.get("GITHUB_TOKEN")
        self.transport = transport

    def get(self, endpoint: str) -> dict:
        if not endpoint.startswith("/") or "//" in endpoint or "://" in endpoint:
            raise ValueError("GitHub API endpoints must be root-relative")
        url = "https://api.github.com" + endpoint
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "kstack/0.1", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = urllib.request.Request(url, headers=headers)
        try:
            if self.transport:
                return self.transport(request)
            # HTTPS redirects to a different host must not receive the GitHub token.
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, request, fp, code, msg, headers, newurl):
                    raise GitHubError("Redirects disabled for authenticated GitHub requests")
            opener = urllib.request.build_opener(NoRedirect())
            with opener.open(request, timeout=12) as response:
                if int(response.headers.get("Content-Length", 0)) > 3_000_000:
                    raise GitHubError("Response too large")
                return json.loads(response.read(3_000_001))
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            raise GitHubError(f"GitHub request failed: {getattr(exc, 'code', type(exc).__name__)}") from exc

    def repository(self, repo: str) -> dict:
        return self.get("/repos/" + valid_repo(repo))

    def head(self, repo: str, branch: str) -> str:
        if not branch or ".." in branch or branch.startswith("/") or "?" in branch:
            raise ValueError("Invalid branch")
        data = self.get("/repos/" + valid_repo(repo) + "/commits/" + urllib.parse.quote(branch, safe=""))
        sha = data.get("sha", "")
        if not SHA.fullmatch(sha):
            raise GitHubError("Invalid commit response")
        return sha

    def tree(self, repo: str, sha: str) -> list[dict]:
        if not SHA.fullmatch(sha):
            raise ValueError("Expected immutable SHA")
        data = self.get(f"/repos/{valid_repo(repo)}/git/trees/{sha}?recursive=1")
        if data.get("truncated"):
            raise GitHubError("GitHub tree truncated; cannot inspect entire package")
        return data.get("tree", [])

    def skill(self, repo: str, path: str, sha: str) -> str:
        valid_repo(repo)
        valid_path(path)
        if not SHA.fullmatch(sha):
            raise ValueError("Immutable 40-char commit required")
        escaped = "/".join(urllib.parse.quote(s, safe="") for s in path.split("/"))
        data = self.get(f"/repos/{repo}/contents/{escaped}?ref={sha}")
        if data.get("type") != "file" or data.get("encoding") != "base64":
            raise GitHubError("Unsupported skill payload")
        if int(data.get("size", 0)) > 80_000:
            raise GitHubError("Skill exceeds size cap")
        try:
            content = base64.b64decode(data["content"], validate=False)
            if len(content) > 80_000:
                raise GitHubError("Skill exceeds size cap")
            return content.decode("utf-8")
        except (ValueError, KeyError, UnicodeError) as exc:
            raise GitHubError("Malformed skill contents") from exc
