#!/usr/bin/env python3
import argparse
import hashlib
import json
import pathlib
import shutil
import sys

SCHEMA = "dcoir.chatgpt_staging.github_artifact_readback_manifest.v1"
INVALID_REQUEST_IDS = {".", ".."}
OUT_ROOT = pathlib.Path(".github/chatgpt_staging/out")
REPORT_ROOT = pathlib.Path(".github/chatgpt_staging/status_reports/chatgpt-github-artifact-readback")


def validate_request_id(request_id: str) -> None:
    if request_id in INVALID_REQUEST_IDS:
        raise SystemExit(f"Unsafe request_id: {request_id!r}")


def validate_artifact_subpath(artifact_subpath: str) -> None:
    if artifact_subpath:
        pure = pathlib.PurePosixPath(artifact_subpath)
        if artifact_subpath.startswith("/") or ".." in pure.parts:
            raise SystemExit("artifact_subpath must be relative and must not contain parent traversal")


def validate_stage_paths(request_id: str, out_dir: pathlib.Path, report_dir: pathlib.Path) -> None:
    validate_request_id(request_id)
    expected_out_root = OUT_ROOT.resolve(strict=False)
    expected_report_root = REPORT_ROOT.resolve(strict=False)
    resolved_out_dir = out_dir.resolve(strict=False)
    resolved_report_dir = report_dir.resolve(strict=False)
    if resolved_out_dir.parent != expected_out_root or resolved_out_dir.name != request_id:
        raise SystemExit(f"Refusing unsafe out_dir outside {OUT_ROOT}: {out_dir}")
    if resolved_report_dir.parent != expected_report_root or resolved_report_dir.name != request_id:
        raise SystemExit(f"Refusing unsafe report_dir outside {REPORT_ROOT}: {report_dir}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--report-dir", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--artifact-name", default="")
    parser.add_argument("--artifact-id", default="")
    parser.add_argument("--artifact-subpath", default="")
    args = parser.parse_args()

    download_dir = pathlib.Path(args.download_dir)
    out_dir = pathlib.Path(args.out_dir)
    report_dir = pathlib.Path(args.report_dir)

    validate_artifact_subpath(args.artifact_subpath)
    validate_stage_paths(args.request_id, out_dir, report_dir)

    if not download_dir.exists():
        raise SystemExit(f"Downloaded artifact path not found: {download_dir}")

    source_root = download_dir / args.artifact_subpath if args.artifact_subpath else download_dir
    if not source_root.exists():
        raise SystemExit(f"artifact_subpath not found inside artifact: {args.artifact_subpath}")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    files: list[dict[str, object]] = []
    if source_root.is_file():
        rel = pathlib.Path(source_root.name)
        target = out_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_root, target)
        data = target.read_bytes()
        files.append({"path": rel.as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    else:
        for src in sorted(source_root.rglob("*")):
            if src.is_dir():
                continue
            rel = src.relative_to(source_root)
            target = out_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            data = target.read_bytes()
            files.append({"path": rel.as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})

    if not files:
        raise SystemExit("Artifact extraction produced no files to stage")

    manifest = {
        "schema": SCHEMA,
        "request_id": args.request_id,
        "source_run_id": args.source_run_id,
        "artifact_name": args.artifact_name,
        "artifact_id": args.artifact_id,
        "artifact_subpath": args.artifact_subpath,
        "file_count": len(files),
        "files": files,
    }
    (out_dir / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# GitHub artifact readback manifest",
        "",
        f"- request_id: `{args.request_id}`",
        f"- source_run_id: `{args.source_run_id}`",
        f"- artifact_name: `{args.artifact_name or '(downloaded by id)'}`",
        f"- artifact_id: `{args.artifact_id or '(downloaded by name)'}`",
        f"- artifact_subpath: `{args.artifact_subpath or '.'}`",
        f"- file_count: `{len(files)}`",
        "",
        "## Files",
        "",
    ]
    for entry in files:
        lines.append(f"- `{entry['path']}` | bytes={entry['bytes']} | sha256=`{entry['sha256']}`")
    (out_dir / "artifact_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
