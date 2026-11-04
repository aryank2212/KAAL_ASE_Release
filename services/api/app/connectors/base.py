import importlib.metadata
import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod

MAX_OUTPUT = 1_000_000


class ConnectorError(RuntimeError):
    pass


def tools_dir() -> str:
    return os.environ.get("KAAL_TOOLS_DIR", os.path.expanduser("~/.kaal/tools"))


def find_binary(name: str, env_var: str | None = None) -> str | None:
    """Env override, then <KAAL_TOOLS_DIR>/<name>-venv/bin, then next to the interpreter, then PATH."""
    if env_var and os.environ.get(env_var):
        p = os.environ[env_var]
        return p if os.path.isfile(p) and os.access(p, os.X_OK) else None
    sub, ext = ("Scripts", ".exe") if os.name == "nt" else ("bin", "")
    iso = os.path.join(tools_dir(), f"{name.lower()}-venv", sub, name + ext)
    if os.path.isfile(iso) and os.access(iso, os.X_OK):
        return iso
    local = os.path.join(os.path.dirname(sys.executable), name + (".exe" if os.name == "nt" else ""))
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    return shutil.which(name)


# In a frozen build (Windows installer) there is no `maigret` program on disk, so the app re-runs itself as the tool.
FROZEN_TOOLS = {"maigret": "maigret", "sherlock": "sherlock_project"}


def tool_cmd(name: str, env_var: str | None = None) -> list[str] | None:
    exe = find_binary(name, env_var)
    if exe:
        return [exe]
    if getattr(sys, "frozen", False) and name in FROZEN_TOOLS:
        return [sys.executable, "--run-tool", FROZEN_TOOLS[name]]
    return None


def run_cli(args: list[str], timeout: int, stdout_only: bool = False) -> str:
    """Run a tool without a shell. Output is capped; the process is killed on timeout."""
    env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "/tmp"), "LANG": "C.UTF-8"}
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout, env=env, check=False)
    except subprocess.TimeoutExpired:
        raise ConnectorError(f"{os.path.basename(args[0])} timed out after {timeout}s")
    if stdout_only:
        return p.stdout[:MAX_OUTPUT].decode("utf-8", "replace")
    return (p.stdout[:MAX_OUTPUT] + b"\n" + p.stderr[:20_000]).decode("utf-8", "replace")


def pkg_version(dist: str) -> str:
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


class Connector(ABC):
    name: str = ""
    kind: str = ""            # domain | username | phone | image | topic
    license: str = ""
    description: str = ""
    dist: str = ""            # pip distribution name for version reporting
    people_adjacent = False   # username lookups: require the analyst's lawful-use acknowledgment

    def available(self) -> bool:
        return True

    def setup_hint(self) -> str | None:
        """Why an installed connector is not ready yet (credentials, models). None when ready."""
        return None

    def status(self) -> str:
        return "ready" if self.available() and not self.setup_hint() else ("needs_setup" if self.available() else "not_installed")

    def version(self) -> str:
        return pkg_version(self.dist) if self.dist else "n/a"

    @abstractmethod
    def normalise(self, target: str) -> str: ...

    @abstractmethod
    def run(self, target: str) -> dict:
        """Return {outputs, source_references, confidence, warnings}."""
