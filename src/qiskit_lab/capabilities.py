"""Credential-free metadata checks for the documented optional environments."""
from __future__ import annotations

import importlib.metadata
import platform
import sys

PROFILES = {
    "sqd": {"qiskit": "2.6.2", "qiskit-addon-sqd": "0.14.1", "pyscf": "2.15.0"},
    "fermionic": {"qiskit": "2.6.2", "qiskit-fermions": "0.4.1"},
    "fermionic-sim": {
        "qiskit": "2.6.2", "qiskit-fermions": "0.4.1", "ffsim": "0.0.86", "pyscf": "2.15.0",
    },
}


def recipe_platform_supported(profile: str) -> bool:
    """Check known wheel targets, not whether a local native library can load."""
    machine = platform.machine().lower()
    if not (3, 11) <= sys.version_info[:2] < (3, 14):
        return False
    if sys.platform == "linux":
        libc, version = platform.libc_ver()
        return machine in {"x86_64", "aarch64"} and libc == "glibc" and tuple(
            int(part) for part in version.split(".")[:2] if part.isdigit()
        ) >= (2, 28)
    if sys.platform == "darwin":
        return machine == "arm64" or (machine == "x86_64" and profile != "fermionic-sim")
    return sys.platform == "win32" and machine in {"amd64", "x86_64"}


def optional_capabilities(requested: list[str] | None = None) -> dict:
    """Never import optional code, inspect accounts, run installers or query IBM."""
    result = {}
    for profile in requested or PROFILES:
        packages = {}
        for name, expected in PROFILES[profile].items():
            try:
                installed = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                packages[name] = {"expected": expected, "version": None, "status": "missing"}
            except Exception:  # Metadata may be corrupt; never include arbitrary exception text.
                packages[name] = {"expected": expected, "version": None, "status": "metadata_error"}
            else:
                packages[name] = {
                    "expected": expected, "version": installed,
                    "status": "installed" if installed == expected else "version_mismatch",
                }
        supported = recipe_platform_supported(profile)
        states = {package["status"] for package in packages.values()}
        status = next((state for state in ("metadata_error", "missing", "version_mismatch") if state in states),
                      "installed")
        if not supported:
            status = "unsupported_platform"
        result[profile] = {
            "status": status,
            "packages": packages,
            "recipe_platform_supported": supported,
            "check": "distribution_metadata_only",
            "runtime_verified": False,
            "next_step": (
                f"See docs/optional-capabilities.md; use the isolated '{profile}' profile and its smoke check."
                if supported else
                "No wheel-only recipe for this Python/platform; use a documented Linux/macOS/Windows target. "
                "See docs/optional-capabilities.md."
            ),
        }
    return result
