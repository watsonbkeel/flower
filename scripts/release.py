"""Prepare a reviewable immutable release bundle; never deploy it."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile


def validate_manifest(manifest):
    sha = manifest.get("commit", "")
    if not re.fullmatch("[0-9a-f]{40}", sha):
        raise ValueError("full commit SHA required")
    if manifest.get("spec_version") != "2.2.2":
        raise ValueError("v2.2.2 required")
    images = manifest.get("images", {})
    if images.get("app", {}).get("tag") != "flower-app:" + sha:
        raise ValueError("immutable app image tag required")
    for value in images.values():
        if not re.fullmatch("sha256:[0-9a-f]{64}", value.get("id", "")):
            raise ValueError("record each inspected image ID")
    if set(images) != {"app", "postgres", "proxy"}:
        raise ValueError("all release images required")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inspect-images", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root).strip():
        raise SystemExit("Commit changes before generating a release bundle")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    release = args.output.resolve() / sha
    if release.is_relative_to(Path("/srv/flower")):
        raise SystemExit("This preparation tool only writes development bundles")
    release.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryFile() as archive:
        subprocess.run(["git", "archive", sha], cwd=root, stdout=archive, check=True)
        archive.seek(0)
        with tarfile.open(fileobj=archive) as tar:
            tar.extractall(release, filter="data")
    images = {
        name: {"tag": tag, "id": None}
        for name, tag in {
            "app": "flower-app:" + sha,
            "postgres": "postgres:17.11",
            "proxy": "nginxinc/nginx-unprivileged:1.28.0-alpine",
        }.items()
    }
    if args.inspect_images:
        for value in images.values():
            inspected = json.loads(
                subprocess.check_output(["docker", "image", "inspect", value["tag"]])
            )[0]
            value["id"] = inspected["Id"]
            value["digests"] = inspected.get("RepoDigests", [])
    manifest = {
        "spec_version": "2.2.2",
        "commit": sha,
        "images": images,
        "migration": "0003_retention",
        "state": "READY" if args.inspect_images else "NOT_BUILT",
        "files": {
            p.relative_to(release).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in release.rglob("*")
            if p.is_file()
        },
    }
    if args.inspect_images:
        validate_manifest(manifest)
    (release / "release.json").write_text(json.dumps(manifest, indent=2))
    image_env = (
        "".join(
            f"{key}={images[name]['id']}\n"
            for key, name in [("POSTGRES_IMAGE", "postgres"), ("PROXY_IMAGE", "proxy")]
        )
        if args.inspect_images
        else ""
    )
    (release / "release.env").write_text("IMAGE_TAG=" + sha + "\n" + image_env)
    print(release)


if __name__ == "__main__":
    main()
