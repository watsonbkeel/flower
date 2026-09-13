"""Read-only shared-host snapshot; run only in a deployment validation window."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

COMMANDS = {
    "ports": ["ss", "-lntup"],
    "services": ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager"],
    "service_state": [
        "systemctl",
        "show",
        "nginx",
        "nox-brain",
        "city-front",
        "tailscaled",
        "openvpn-server@server",
        "-p",
        "ActiveState,SubState,MainPID,NRestarts",
    ],
    "ufw": ["ufw", "status", "verbose"],
    "nft": ["nft", "list", "ruleset"],
    "routes": ["ip", "route", "show", "table", "all"],
    "addresses": ["ip", "-brief", "address"],
    "tailscale": ["tailscale", "status", "--json"],
    "nginx_test": ["nginx", "-t"],
}


def snapshot():
    result = {}
    for name, command in COMMANDS.items():
        try:
            run = subprocess.run(command, capture_output=True, text=True, timeout=20)
            result[name] = {
                "returncode": run.returncode,
                "stdout": run.stdout,
                "stderr": run.stderr,
            }
        except (OSError, subprocess.TimeoutExpired) as exc:
            result[name] = {"returncode": -1, "error": type(exc).__name__}
    result["nginx_hashes"] = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in Path("/etc/nginx").rglob("*")
        if path.is_file()
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    result = snapshot()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    args.output.chmod(0o600)
    if args.compare:
        previous = json.loads(args.compare.read_text())
        print(json.dumps({"changed": [key for key in result if result[key] != previous.get(key)]}))
    print("Snapshot contains network metadata; review before publishing evidence.")


if __name__ == "__main__":
    main()
