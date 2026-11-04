"""Single entry point for the installed builds (.deb, Arch package, Windows .exe) and for `python -m app.launcher`.

First run: creates the data directory, a SQLite database and a random API key (saved with owner-only permissions).
Settings come from, in order: real environment variables, the env file (KAAL_ENV_FILE, /etc/kaal-ase/kaal-ase.env), defaults.
"""
import argparse
import os
import secrets
import socket
import sys
import threading
import time
from pathlib import Path

VERSION = "2.2.0"
LOOPBACK = ("127.0.0.1", "::1", "localhost")


def default_data_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "KAAL-ASE"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "kaal-ase"


def load_env_file(path: Path) -> int:
    n = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v
            n += 1
    return n


def ensure_api_key(data_dir: Path) -> tuple[str, bool]:
    """Returns (key, generated_now). A key from the environment always wins."""
    if os.environ.get("KAAL_API_KEY", "").strip():
        return os.environ["KAAL_API_KEY"].strip(), False
    f = data_dir / "api_key"
    if f.is_file() and f.read_text().strip():
        return f.read_text().strip(), False
    key = secrets.token_urlsafe(32)
    fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(key + "\n")
    return key, True


def _open_when_ready(host: str, port: int, url: str) -> None:
    for _ in range(100):
        try:
            socket.create_connection((host if host != "0.0.0.0" else "127.0.0.1", port), 0.3).close()
            break
        except OSError:
            time.sleep(0.2)
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass


def prepare(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="kaal-ase", description="KAAL ASE API and console")
    ap.add_argument("--host", help="bind address (default 127.0.0.1; KAAL_HOST)")
    ap.add_argument("--port", type=int, help="port (default 8140; KAAL_PORT)")
    ap.add_argument("--data-dir", help="data directory (KAAL_DATA_DIR)")
    ap.add_argument("--env-file", help="env file with KEY=VALUE lines (KAAL_ENV_FILE)")
    ap.add_argument("--open", action="store_true", help="open the console in your browser (loopback only)")
    ap.add_argument("--version", action="store_true")
    a = ap.parse_args(argv)
    if a.version:
        print(f"KAAL ASE {VERSION}")
        raise SystemExit(0)
    env_file = a.env_file or os.environ.get("KAAL_ENV_FILE") or ("/etc/kaal-ase/kaal-ase.env" if os.name != "nt" else "")
    if env_file:
        load_env_file(Path(env_file))
    data_dir = Path(a.data_dir or os.environ.get("KAAL_DATA_DIR") or default_data_dir()).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["KAAL_DATA_DIR"] = str(data_dir)
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + (data_dir / "kaal.db").as_posix())
    ev = Path(os.environ.get("EVIDENCE_DIR") or data_dir / "evidence")
    ev.mkdir(parents=True, exist_ok=True)
    os.environ["EVIDENCE_DIR"] = str(ev)
    if getattr(sys, "frozen", False):            # Windows installer: ExifTool ships next to the executable
        for name in ("exiftool.exe", "exiftool"):
            cand = Path(sys.executable).parent / "exiftool" / name
            if cand.is_file():
                os.environ.setdefault("EXIFTOOL_BIN", str(cand))
                break
    key, fresh = ensure_api_key(data_dir)
    os.environ["KAAL_API_KEY"] = key
    a.host = a.host or os.environ.get("KAAL_HOST") or "127.0.0.1"
    a.port = a.port or int(os.environ.get("KAAL_PORT") or 8140)
    a.data_dir, a.key, a.fresh_key = data_dir, key, fresh
    return a


def run_tool(module: str, args: list[str]) -> None:
    """Frozen builds: `kaal-ase.exe --run-tool maigret ...` runs a bundled tool in-process."""
    import runpy
    if module not in ("maigret", "sherlock_project"):
        raise SystemExit(f"unknown tool: {module}")
    sys.argv = [module, *args]
    runpy.run_module(module, run_name="__main__", alter_sys=True)


def main(argv=None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--run-tool"] and len(argv) >= 2:
        return run_tool(argv[1], argv[2:])
    a = prepare(argv)
    import uvicorn                       # imported after the environment is final: app.config reads it at import time
    from app.main import app
    shown = "127.0.0.1" if a.host in ("0.0.0.0", "::") else a.host
    url = f"http://{shown}:{a.port}/ui/"
    print(f"KAAL ASE {VERSION}\n  console : {url}\n  data    : {a.data_dir}\n  API key : {a.data_dir / 'api_key'}"
          f"{'  (generated now)' if a.fresh_key else ''}", flush=True)
    if a.open and a.host in LOOPBACK:
        threading.Thread(target=_open_when_ready, args=(shown, a.port, url + "#key=" + a.key), daemon=True).start()
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")


if __name__ == "__main__":
    main(sys.argv[1:])
