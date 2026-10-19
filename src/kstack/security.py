"""Defence-in-depth *screening*, never a security guarantee for untrusted skills."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import PurePosixPath, PureWindowsPath

NAME = re.compile(r"^(?=.{1,64}$)(?:[a-z0-9]|[a-z0-9][a-z0-9-]*[a-z0-9])$")
REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
SHA = re.compile(r"^[a-f0-9]{40}$")
SKILL_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
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


def is_safe_relative_path(value: str) -> bool:
    """Check a slash-separated relative path against POSIX and Windows roots."""
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts) or PurePosixPath(value).is_absolute():
        return False
    windows_paths = [PureWindowsPath(value), *(PureWindowsPath(part) for part in parts)]
    return not any(path.drive or path.root or path.is_absolute() for path in windows_paths)


def valid_path(value: str) -> str:
    path = PurePosixPath(value) if isinstance(value, str) else PurePosixPath("")
    if not is_safe_relative_path(value) or path.name != "SKILL.md":
        raise ValueError("Path must be a relative path ending in SKILL.md")
    return value


def _yaml_text(value: str, field: str) -> str:
    """Parse one conservative YAML string scalar without a runtime YAML dependency.

    This is intentionally a documented subset of YAML: strings may be plain,
    single quoted or JSON-compatible double quoted. YAML tags, aliases, flow
    collections and implicit non-string values are rejected instead of guessed.
    """
    value = value.strip()
    quote = None
    escaped = False
    index = 0
    while index < len(value):
        char = value[index]
        if quote == '"':
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quote = None
            index += 1
        elif quote == "'":
            if char == "'":
                if index + 1 < len(value) and value[index + 1] == "'":
                    index += 2
                    continue
                quote = None
            index += 1
        elif char in ('"', "'"):
            quote = char
            index += 1
        elif char == "#" and (index == 0 or value[index - 1].isspace()):
            value = value[:index].rstrip()
            break
        else:
            index += 1
    if quote is not None:
        raise ValueError(f"Malformed quoted YAML value for {field}")
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed double-quoted YAML value for {field}") from exc
        if not isinstance(parsed, str):
            raise ValueError(f"Expected a string value for {field}")
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise ValueError(f"Malformed single-quoted YAML value for {field}")
        inner = value[1:-1]
        out = []
        index = 0
        while index < len(inner):
            if inner[index] == "'":
                if index + 1 >= len(inner) or inner[index + 1] != "'":
                    raise ValueError(f"Malformed single-quoted YAML value for {field}")
                out.append("'")
                index += 2
            else:
                out.append(inner[index])
                index += 1
        return "".join(out)
    if not value or value[0] in "&*![]{}|>":
        raise ValueError(f"Expected a supported YAML string scalar for {field}")
    if re.fullmatch(r"(?:null|true|false|~|[-+]?(?:[0-9]+(?:\\.[0-9]*)?|\\.[0-9]+)(?:[eE][-+]?[0-9]+)?)", value, re.IGNORECASE):
        raise ValueError(f"Quote non-string YAML value for {field}")
    return value


def _block_scalar(lines: list[str], start: int, marker: str, field: str) -> tuple[str, int]:
    """Read a literal/folded YAML block scalar with inferred indentation."""
    cursor = start
    content_lines = []
    indent = None
    while cursor < len(lines):
        line = lines[cursor]
        if line.strip() and not line[0].isspace():
            break
        if line.strip():
            current_indent = len(line) - len(line.lstrip(" "))
            if "\t" in line[:current_indent] or current_indent == 0:
                raise ValueError(f"Invalid indentation in block scalar for {field}")
            if indent is None:
                indent = current_indent
            elif current_indent < indent:
                raise ValueError(f"Invalid indentation in block scalar for {field}")
            content_lines.append(line[indent:])
        else:
            content_lines.append("")
        cursor += 1
    while content_lines and not content_lines[-1]:
        content_lines.pop()
    if marker.startswith(">"):
        pieces = []
        for line in content_lines:
            if not line:
                pieces.append("\n")
            elif pieces and pieces[-1] != "\n":
                pieces.append(" " + line)
            else:
                pieces.append(line)
        text = "".join(pieces)
    else:
        text = "\n".join(content_lines)
    chomping = marker[1:]
    if chomping == "-":
        text = text.rstrip("\n")
    elif chomping != "+":
        text = text.rstrip("\n") + "\n"
    return text, cursor


def _frontmatter(content: str) -> tuple[dict, str]:
    normalized = content.replace("\r\n", "\n")
    lines = normalized.split("\n")
    if not lines or lines[0] != "---":
        raise ValueError("Skill needs SKILL.md YAML frontmatter")
    try:
        close = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("Malformed skill frontmatter") from exc
    if len("\n".join(lines[:close + 1]).encode("utf-8")) > 16_000:
        raise ValueError("Skill frontmatter exceeds the 16 KB bound")
    data = {}
    index = 1
    while index < close:
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        if line[0].isspace():
            raise ValueError("Unexpected indentation in skill frontmatter")
        key, sep, raw = line.partition(":")
        key = key.strip()
        if not sep or not re.fullmatch(r"[a-z][a-z0-9-]*", key):
            raise ValueError("Malformed skill frontmatter field")
        if key not in SKILL_FIELDS:
            raise ValueError(f"Unsupported skill frontmatter field: {key}")
        if key in data:
            raise ValueError(f"Duplicate skill frontmatter field: {key}")
        raw = raw.strip()
        index += 1
        if key == "metadata":
            if raw:
                raise ValueError("metadata must be a YAML mapping")
            metadata = {}
            while index < close:
                child = lines[index]
                if not child.strip() or child.lstrip().startswith("#"):
                    index += 1
                    continue
                if not child[0].isspace():
                    break
                if not child.startswith("  ") or child.startswith("   "):
                    raise ValueError("metadata entries must use two-space indentation")
                subkey, subsep, subraw = child[2:].partition(":")
                subkey = subkey.strip()
                if not subsep or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", subkey):
                    raise ValueError("Invalid skill metadata key")
                if subkey in metadata:
                    raise ValueError(f"Duplicate skill metadata key: {subkey}")
                value = _yaml_text(subraw, "metadata." + subkey)
                if len(value) > 1024:
                    raise ValueError(f"Skill metadata value is too long: {subkey}")
                metadata[subkey] = value
                index += 1
            data[key] = metadata
            continue
        if raw in ("|", "|-", "|+", ">", ">-", ">+"):
            value, index = _block_scalar(lines[:close], index, raw, key)
        else:
            value = _yaml_text(raw, key)
        data[key] = value
    for required in ("name", "description"):
        if required not in data:
            raise ValueError(f"Skill frontmatter requires {required}")
    if not NAME.fullmatch(data["name"]):
        raise ValueError("Invalid skill name")
    if not data["description"].strip() or len(data["description"]) > 1024:
        raise ValueError("Skill description must be nonempty and at most 1024 characters")
    if "license" in data and not data["license"].strip():
        raise ValueError("Skill license cannot be empty")
    if "compatibility" in data and len(data["compatibility"]) > 500:
        raise ValueError("Skill compatibility must be at most 500 characters")
    if "allowed-tools" in data and not data["allowed-tools"].strip():
        raise ValueError("allowed-tools cannot be empty")
    if not isinstance(data.get("metadata", {}), dict):
        raise ValueError("metadata must be a mapping of string values")
    body = "\n".join(lines[close + 1:]).strip()
    if not body:
        raise ValueError("Skill guidance body cannot be empty")
    return data, body


def parse_skill(content: str) -> dict:
    """Validate Agent Skills metadata using a conservative stdlib YAML subset.

    Supported scalars are plain, single/double quoted, and literal/folded
    description blocks. The optional standard fields and string-to-string
    ``metadata`` map are retained. YAML aliases, tags and collection syntax are
    rejected rather than partially interpreted.
    """
    if not isinstance(content, str) or len(content.encode("utf-8")) > 80_000:
        raise ValueError("Skill exceeds the 80 KB bound")
    data, _body = _frontmatter(content)
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


def is_link_or_junction(path) -> bool:
    """Detect symbolic links and, where the runtime exposes it, Windows junctions."""
    if path.is_symlink():
        return True
    check = getattr(path, "is_junction", None)
    return bool(check and check())
