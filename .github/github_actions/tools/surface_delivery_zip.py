#!/usr/bin/env python3
"""Surface one production delivery zip from a build report.

The bundle/build workflows also upload broad evidence artifacts. This helper
copies the exact generated delivery zip into a clean operator-facing location,
or extracts it there when GitHub's artifact ZIP wrapper should become the
production package ZIP instead of a ZIP containing another ZIP. Optional
manifest files can be written to a separate evidence directory so manifests do
not pollute the direct-download artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_reports(value: Any) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    if isinstance(value, dict):
        report = value.get("report")
        if isinstance(report, dict):
            reports.append(report)
        for child in value.values():
            reports.extend(iter_reports(child))
    elif isinstance(value, list):
        for child in value:
            reports.extend(iter_reports(child))
    return reports


def find_zip_path(report: dict[str, Any]) -> Path:
    candidates: list[str] = []
    direct = report.get("zip_path")
    if isinstance(direct, str) and direct.strip():
        candidates.append(direct)
    for nested_report in iter_reports(report):
        nested = nested_report.get("zip_path")
        if isinstance(nested, str) and nested.strip():
            candidates.append(nested)

    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return path
    raise SystemExit(f"No existing delivery zip found in build report candidates: {candidates}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_zip(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
    return {
        "entry_count": len(names),
        "top_level_entries": sorted({name.split("/", 1)[0] for name in names if name}),
    }


def extract_zip(path: Path, output_dir: Path) -> None:
    with zipfile.ZipFile(path) as zf:
        zf.extractall(output_dir)


def write_manifest(manifest_dir: Path, manifest: dict[str, Any]) -> None:
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "delivery_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (manifest_dir / "delivery_manifest.md").write_text(
        "\n".join(
            [
                "# Delivery artifact manifest",
                "",
                f"- workflow: {manifest['workflow']}",
                f"- artifact_label: {manifest['artifact_label']}",
                f"- delivery_zip_name: {manifest['delivery_zip_name']}",
                f"- delivery_zip_size_bytes: {manifest['delivery_zip_size_bytes']}",
                f"- delivery_zip_sha256: {manifest['delivery_zip_sha256']}",
                f"- source_build_report: {manifest['source_build_report']}",
                "",
                "When extract_for_artifact is true, the direct operator-facing artifact contains the production delivery ZIP contents.",
                "Use the full evidence artifact for this manifest and build reports.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-report", required=True, help="Build report JSON containing the generated zip_path.")
    parser.add_argument("--output-dir", required=True, help="Clean directory for the surfaced delivery artifact.")
    parser.add_argument(
        "--manifest-dir",
        help="Optional separate evidence directory for delivery_manifest.json and delivery_manifest.md.",
    )
    parser.add_argument(
        "--extract-for-artifact",
        action="store_true",
        help="Extract the delivery zip into output-dir so GitHub's artifact ZIP is not a ZIP containing another ZIP.",
    )
    parser.add_argument("--artifact-label", required=True, help="Operator-facing delivery artifact label.")
    parser.add_argument("--workflow-name", required=True, help="Top-level workflow name for manifest/readback.")
    args = parser.parse_args()

    report_path = Path(args.build_report)
    output_dir = Path(args.output_dir)
    report = load_json(report_path)
    zip_path = find_zip_path(report)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    delivery_zip = output_dir / zip_path.name
    if args.extract_for_artifact:
        extract_zip(zip_path, output_dir)
        surfaced_path = output_dir
        surfaced_mode = "extracted_zip_contents"
        manifest_delivery_zip = zip_path
    else:
        shutil.copy2(zip_path, delivery_zip)
        surfaced_path = delivery_zip
        surfaced_mode = "copied_zip_file"
        manifest_delivery_zip = delivery_zip

    manifest = {
        "success": True,
        "workflow": args.workflow_name,
        "artifact_label": args.artifact_label,
        "source_build_report": report_path.as_posix(),
        "source_zip_path": zip_path.as_posix(),
        "source_zip_name": zip_path.name,
        "delivery_zip": manifest_delivery_zip.as_posix(),
        "delivery_zip_name": zip_path.name,
        "delivery_zip_size_bytes": zip_path.stat().st_size,
        "delivery_zip_sha256": sha256_file(zip_path),
        "surfaced_path": surfaced_path.as_posix(),
        "surfaced_mode": surfaced_mode,
        "zip_inspection": inspect_zip(zip_path),
    }
    if args.manifest_dir:
        manifest_dir = Path(args.manifest_dir)
        write_manifest(manifest_dir, manifest)
        manifest["manifest_dir"] = manifest_dir.as_posix()
    else:
        write_manifest(output_dir, manifest)
        manifest["manifest_dir"] = output_dir.as_posix()

    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
