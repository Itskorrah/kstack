"""Defence-in-depth *screening*, never a security guarantee for untrusted skills."""
from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath

NAME = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")
REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
SHA = re.compile(r"^[a-f0-9]{40}$")
# Heuristics intentionally over-block; safe-looking text is NOT proof of safety.
RISK_MARKERS = [
    r"\bcurl\b[^\n]*\|\s*(?:ba)?sh\b", r"\bwget\b[^\n]*\|\s*(?:ba)?sh\b",
    r"\brm\s+-rf\b", r"\bchmod\s+777\b", r"\bsudo\b", r"\bssh-key\b",
    r"\b(?:credential|secret|private.key|api.key|token)\b[^\n]{0,70}\b(?:upload|send|post|exfiltrat)\b",
    r"\b(?:ignore|override|bypass|disable)\b[^\n]{0,60}\b(?:system|developer|safety|security|instruction|policy|approval)\b",
    r"\b(?:run|execute)\b[^\n]{0,70}\b(?:arbitrary|shell|terminal)\b",
    r"\b(?:postinstall|preinstall|hooks?)\b[^\n]{0,50}\b(?:run|execute|script)\b",
    r"\b(?:base64\s+-d|eval\s*\(|exec\s*\()",
]


def valid_repo(value: str) -> str:
    if not REPO.fullmatch(value) or ".." in value:
        raise ValueError("Expected an owner/repository identifier")
    return value


def valid_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or "\\" in value or value.startswith("/") or any(p in ("..", ".", "") for p in value.split("/")) or path.name != "SKILL.md":
        raise ValueError("Path must be a relative path ending in SKILL.md")
    return value


def parse_skill(content: str) -> dict:
    if not isinstance(content, str) or len(content.encode("utf-8")) > 80_000:
        raise ValueError("Skill exceeds the 80 KB bound")
    if not content.startswith("---\n"):
        raise ValueError("Skill needs SKILL.md YAML frontmatter")
    parts = content.split("\n---\n", 1)
    if len(parts) != 2:
        raise ValueError("Malformed skill frontmatter")
    data = {}
    for line in parts[0].splitlines()[1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if sep and key.strip() in ("name", "description"):
            data[key.strip()] = value.strip().strip('"\'')
    if not NAME.fullmatch(data.get("name", "")):
        raise ValueError("Invalid skill name")
    if not 16 <= len(data.get("description", "")) <= 1024:
        raise ValueError("Skill description must specify when to use it")
    if len(parts[1].strip()) < 100:
        raise ValueError("Insufficient skill guidance")
    return data


def screen(content: str, files: list[str] | None = None) -> list[str]:
    findings = [f"risky instruction pattern {i + 1}" for i, p in enumerate(RISK_MARKERS) if re.search(p, content, re.IGNORECASE)]
    if any((not file.endswith(".md")) for file in (files or [])):
        findings.append("non-Markdown contents require manual review")
    # Do not auto-promote executable instructions even if they look harmless.
    if re.search(r"```\s*(?:bash|sh|shell|powershell|python|javascript|js|terminal|zsh|fish|cmd)\b", content, re.IGNORECASE):
        findings.append("executable code fence requires manual review")
    return findings


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
