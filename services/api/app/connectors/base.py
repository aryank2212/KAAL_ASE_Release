import importlib.metadata
import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod

MAX_OUTPUT = 1_000_000


class ConnectorError(RuntimeError):
    pass


def find_binary(name: str, env_var: str | None = None) -> str | None:
    """Look next to the running interpreter (venv/bin) first, then PATH."""
    if env_var and os.environ.get(env_var):
        p = os.environ[env_var]
        return p if os.path.isfile(p) and os.access(p, os.X_OK) else None
    local = os.path.join(os.path.dirname(sys.executable), name)
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    return shutil.which(name)


def run_cli(args: list[str], timeout: int) -> str:
    """Run a tool without a shell. Output is capped; the process is killed on timeout."""
    env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "/tmp"), "LANG": "C.UTF-8"}
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout, env=env, check=False)
    except subprocess.TimeoutExpired:
        raise ConnectorError(f"{os.path.basename(args[0])} timed out after {timeout}s")
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

    def version(self) -> str:
        return pkg_version(self.dist) if self.dist else "n/a"

    @abstractmethod
    def normalise(self, target: str) -> str: ...

    @abstractmethod
    def run(self, target: str) -> dict:
        """Return {outputs, source_references, confidence, warnings}."""
