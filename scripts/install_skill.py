from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy this skill folder into an agent/Codex skills directory.")
    parser.add_argument("--target", required=True, type=Path, help="Parent skills directory")
    parser.add_argument("--name", default="pixel-perfect-diagram-replica")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    destination = args.target.expanduser().resolve() / args.name
    if destination.exists():
        if not args.overwrite:
            raise FileExistsError(f"{destination} already exists; use --overwrite")
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    print(f"Installed skill to {destination}")


if __name__ == "__main__":
    main()
