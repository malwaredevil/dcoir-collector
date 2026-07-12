#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import List

DEFAULT_VERSION = "v9"
DEFAULT_BUNDLE_BASENAME = "dcoir_manual_test_framework_bundle_{version}_full.zip"

REQUIRED_BUNDLE_FILES: List[str] = [
    "run_dcoir_manual_tests.ps1",
    "dcoir_manual_test_runner.py",
    "dcoir_manual_runner_context.py",
    "dcoir_manual_runner_package.py",
    "dcoir_manual_runner_checks.py",
    "dcoir_manual_runner_checks_part_01.py",
    "dcoir_manual_runner_checks_part_02.py",
    "dcoir_manual_runner_flow.py",
    "dcoir_manual_test_control.json",
    "README_FIRST.txt",
    "install_and_run_from_downloads.ps1",
    "DCOIR_manual_test_plan.md",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_bundle(source_dir: Path, output_dir: Path, version: str, output_name: str | None) -> dict:
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    missing = [name for name in REQUIRED_BUNDLE_FILES if not (source_dir / name).is_file()]
    if missing:
        raise SystemExit("Missing required manual-test framework file(s): " + ", ".join(missing))

    bundle_name = output_name or DEFAULT_BUNDLE_BASENAME.format(version=version)
    if not bundle_name.lower().endswith(".zip"):
        raise SystemExit("Output name must end with .zip")

    bundle_path = output_dir / bundle_name
    manifest_rows = []

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel_name in REQUIRED_BUNDLE_FILES:
            src = source_dir / rel_name
            zf.write(src, arcname=rel_name)
            manifest_rows.append({
                "path": rel_name,
                "size_bytes": src.stat().st_size,
                "sha256": sha256_file(src),
            })

        manifest = {
            "bundle_name": bundle_name,
            "bundle_version": version,
            "source_dir": str(source_dir),
            "files": manifest_rows,
            "run_command": "powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\run_dcoir_manual_tests.ps1",
            "install_helper": "powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\install_and_run_from_downloads.ps1 -BundlePath <path-to-bundle-zip>",
        }
        zf.writestr("manual_test_framework_bundle_manifest.json", json.dumps(manifest, indent=2) + "\n")

    report = {
        "success": True,
        "bundle_path": str(bundle_path),
        "bundle_sha256": sha256_file(bundle_path),
        "bundle_size_bytes": bundle_path.stat().st_size,
        "bundle_version": version,
        "included_files": REQUIRED_BUNDLE_FILES,
    }
    report_path = output_dir / (bundle_path.stem + ".report.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the DCOIR manual-test framework download bundle.")
    ap.add_argument("--source-dir", default=str(Path(__file__).resolve().parent), help="Directory containing the manual-test framework source files.")
    ap.add_argument("--output-dir", default=str(Path(__file__).resolve().parent / "out_manual_test_framework_bundle"), help="Directory where the ZIP and report should be written.")
    ap.add_argument("--version", default=DEFAULT_VERSION, help="Bundle version token used in the default output filename, for example v9.")
    ap.add_argument("--output-name", default=None, help="Optional explicit ZIP filename.")
    args = ap.parse_args()

    report = build_bundle(Path(args.source_dir), Path(args.output_dir), args.version, args.output_name)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
