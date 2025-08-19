# main.py
# Portable Streamlit launcher — use this file as the single entrypoint in any project.

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path

def find_app_file(cli_app: str | None) -> Path:
    """
    Resolve the app file path by priority:
    1) --app CLI argument
    2) serve-config.json -> keys: ["main_file", "streamlit_app", "app"]
    3) fallback: app.py in current directory
    """
    if cli_app:
        p = Path(cli_app).expanduser()
        if p.exists():
            return p.resolve()
        print(f"[main] --app provided but not found: {p}")
        sys.exit(1)

    # Read serve-config.json if present
    for cfg_name in ("serve-config.json", "serve_config.json", ".serve-config.json"):
        cfg_path = Path(cfg_name)
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                for k in ("main_file", "streamlit_app", "app"):
                    val = data.get(k)
                    if isinstance(val, str) and val.strip():
                        p = Path(val).expanduser()
                        if p.exists():
                            return p.resolve()
                        print(f"[main] Config '{cfg_name}' points to non-existent app: {p}")
            except Exception as e:
                print(f"[main] Warning: failed reading {cfg_name}: {e}")

    # Fallback: app.py
    p = Path("app.py")
    if p.exists():
        return p.resolve()

    print("[main] Could not find an app file. Provide --app or create app.py")
    sys.exit(1)

def ensure_streamlit_available():
    try:
        import streamlit  # noqa: F401
    except Exception:
        print(
            "[main] Streamlit is not installed in this environment.\n"
            "       Install it then rerun:\n"
            "       pip install streamlit\n"
        )
        sys.exit(1)

def run_streamlit(app_path: Path, port: int, headless: bool, extra: list[str]):
    # Mark that we’re launching via main to avoid any self re-exec code in the app.
    env = os.environ.copy()
    env["APP_BOOTSTRAPPED"] = "1"

    # Respect common envs (optional & safe defaults)
    env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

    # Build base command
    cmd = [
        sys.executable, "-m", "streamlit", "run", str(app_path),
        "--server.port", str(port),
    ]
    if headless:
        cmd += ["--server.headless", "true"]

    # Forward any extra raw args directly to Streamlit
    if extra:
        cmd += extra

    print("Interpreter:", sys.executable)
    print("Running:", app_path)
    print(f"Port: {port}  Headless: {headless}")
    # Example: streamlit accepts more flags; pass via: py -m main -- --server.address 0.0.0.0
    return subprocess.call(cmd, env=env)

def main():
    parser = argparse.ArgumentParser(
        description="Portable Streamlit launcher (single entrypoint)."
    )
    parser.add_argument("--app", help="Path to Streamlit app file (e.g., app.py)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("STREAMLIT_PORT", "8501")),
                        help="Port to serve on (default: 8501 or $STREAMLIT_PORT)")
    parser.add_argument("--headless", action="store_true",
                        help="Run in headless mode (no browser auto-open)")
    # Everything after `--` will be forwarded to Streamlit directly:
    # e.g., py -m main -- --server.address 0.0.0.0
    args, extra = parser.parse_known_args()

    app_path = find_app_file(args.app)
    ensure_streamlit_available()
    rc = run_streamlit(app_path, args.port, args.headless, extra)
    sys.exit(rc)

if __name__ == "__main__":
    main()
