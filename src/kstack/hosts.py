"""Honest local host capability and installation inspection."""
from __future__ import annotations

import shutil
from pathlib import Path
from .installer import doctor
from .external import list_external

HOST_BINARIES = {"codex": "codex", "claude": "claude"}


def inspect_host(root: Path, state: Path, host: str, scope: str = "global", project: Path | None = None) -> dict:
    if host not in HOST_BINARIES:
        raise ValueError("Unsupported coding host")
    binary = shutil.which(HOST_BINARIES[host])
    configured = doctor(root, state, host, scope, project)
    external = list_external(host, scope, project)
    return {"host": host, "binary_found": bool(binary), "binary_path": binary,
            "kstack_installed_integrity": configured["ok"], "external_installation_integrity": external["ok"],
            "external_packages": external["packages"],
            "invocation_verified": False, "implicit_activation_verified": False,
            "note": "Presence on PATH does not prove host version, authentication, discovery or invocation."}
