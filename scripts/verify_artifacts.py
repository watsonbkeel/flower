"""Local delivery checks; does not inspect or mutate external production systems."""

import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


def main():
    root = Path(__file__).resolve().parents[1]
    spec = root / "docs/specs/智慧守候_v2.2.2_Server-Integrated_冻结基线开发实施规格.md"
    digest = hashlib.sha256(spec.read_bytes()).hexdigest()
    assert digest == "4481d48605aec47660d2cdefb7a004ed2169bb8531302ecdf803c3c12718cf95"
    paths = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
        )
        .decode()
        .split("\0")
    )
    secrets = []
    local = root / ".runtime/dev-config.json"
    if local.exists():
        secrets = [
            value.encode()
            for value in json.loads(local.read_text()).values()
            if isinstance(value, str) and len(value) >= 32
        ]
    leaked = []
    for name in paths:
        path = root / name
        if path.is_file() and any(value in path.read_bytes() for value in secrets):
            leaked.append(name)
    assert not leaked, "A runtime secret appeared in a deliverable"
    suite = (
        ET.parse(root / "evidence/stage8-deployment-sequence-postgres.xml")
        .getroot()
        .find("testsuite")
    )
    assert suite.attrib["failures"] == "0" and suite.attrib["errors"] == "0"
    subprocess.run(["git", "diff", "--check"], cwd=root, check=True)
    result = {
        "spec_version": "2.2.2",
        "spec_sha256": digest,
        "runtime_secret_leaks": leaked,
        "python_tests": int(suite.attrib["tests"]),
        "failures": 0,
        "errors": 0,
        "production_audit_repeated": False,
        "production_deployment": "NOT_RUN",
        "physical_acceptance": "BLOCKED",
    }
    (root / "evidence/delivery-checks.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
