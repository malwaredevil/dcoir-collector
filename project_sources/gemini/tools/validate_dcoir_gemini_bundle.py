#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from lib.gemini_bundle_validation import validate_bundle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    return validate_bundle(Path(args.source_root), Path(args.output_dir))


if __name__ == '__main__':
    raise SystemExit(main())
