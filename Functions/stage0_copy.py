#!/usr/bin/env python3

import shutil
import sys
from pathlib import Path


def default_output(src: Path) -> Path:
    if "_original" in src.stem:
        return src.with_name(src.stem.replace("_original", "_working") + src.suffix)
    return src.with_name(src.stem + ".working" + src.suffix)


def make_working_copy(src: Path, dst: Path, force: bool = False) -> Path:
    if not src.is_file():
        raise FileNotFoundError(f"input file does not exist: {src}")
    if dst.exists() and not force:
        raise FileExistsError(
            f"output already exists: {dst}\n"
            f"refusing to overwrite (use --force to override)"
        )
    shutil.copy2(src, dst)   # copy contents + metadata, byte-for-byte
    return dst


def main():
    args = [a for a in sys.argv[1:] if a != "--force"]
    force = "--force" in sys.argv[1:]

    if not args or len(args) > 2:
        print("usage: python stage0_copy.py X_original.md [output.md] [--force]")
        sys.exit(1)

    src = Path(args[0])
    dst = Path(args[1]) if len(args) == 2 else default_output(src)

    try:
        out = make_working_copy(src, dst, force=force)
    except (FileNotFoundError, FileExistsError) as e:
        print(f"error: {e}")
        sys.exit(1)

    print(f"working copy created: {out}")


if __name__ == "__main__":
    main()
