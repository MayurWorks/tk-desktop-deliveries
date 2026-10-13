# MIT License
#
# Copyright (c) 2026 SlateX
#
# Delivery manifest and checksums. Pure python (no Qt / sgtk) so it can be unit
# tested and reused by a standalone verify script.
#
# For each delivered shot version two files are written next to the frames:
#   <Shot>_v###_manifest.json  what was delivered, from where, by whom, when
#   checksums.sha256           "<hash>  <file name>" lines, checkable with
#                              `sha256sum -c checksums.sha256` on the receiving end

from __future__ import annotations

import datetime
import getpass
import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

ALGORITHMS = ("sha256", "md5", "none")
CHECKSUM_FILE = "checksums.sha256"
CHUNK = 8 * 1024 * 1024


def file_hash(path: str | os.PathLike, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(shot: dict, delivered: Iterable[tuple[str, str]],
                   algorithm: str = "sha256", user: str | None = None) -> dict:
    """
    ``delivered`` is an iterable of (source_path, delivered_path). Hashes are
    computed from the delivered files, which is what the client receives.
    """
    files = []
    total = 0
    for source, target in delivered:
        size = os.path.getsize(target)
        total += size
        entry = {
            "name": os.path.basename(target),
            "source": str(source),
            "bytes": size,
        }
        if algorithm != "none":
            entry[algorithm] = file_hash(target, algorithm)
        files.append(entry)

    return {
        "project_code": shot.get("project_code"),
        "sequence": shot.get("sequence"),
        "shot": shot.get("shot"),
        "version": shot.get("version_number"),
        "first_frame": shot.get("first_frame"),
        "last_frame": shot.get("last_frame"),
        "frame_count": len(files),
        "total_bytes": total,
        "checksum_algorithm": algorithm,
        "delivered_by": user or _user(),
        "delivered_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": files,
    }


def write_manifest(folder: str | os.PathLike, shot: dict,
                   delivered: Iterable[tuple[str, str]], algorithm: str = "sha256") -> dict:
    """Write the manifest (and checksum file) into ``folder``. Returns the
    manifest dict. Raises ValueError for an unknown algorithm."""
    if algorithm not in ALGORITHMS:
        raise ValueError("checksum algorithm must be one of %s" % (ALGORITHMS,))
    folder = Path(folder)
    manifest = build_manifest(shot, list(delivered), algorithm)

    name = "%s_v%03d_manifest.json" % (shot.get("shot"), int(shot.get("version_number") or 0))
    (folder / name).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    if algorithm == "sha256":
        lines = ["%s  %s" % (f["sha256"], f["name"]) for f in manifest["files"]]
        (folder / CHECKSUM_FILE).write_text("\n".join(lines) + "\n")
    return manifest


def verify_folder(folder: str | os.PathLike) -> list[str]:
    """Re-check a delivered folder against its checksums.sha256. Returns a list
    of problems (empty list = everything matches)."""
    folder = Path(folder)
    checksum_file = folder / CHECKSUM_FILE
    if not checksum_file.is_file():
        return ["%s not found" % CHECKSUM_FILE]
    problems = []
    for line in checksum_file.read_text().splitlines():
        if not line.strip():
            continue
        expected, _, name = line.partition("  ")
        target = folder / name
        if not target.is_file():
            problems.append("missing: %s" % name)
        elif file_hash(target, "sha256") != expected:
            problems.append("checksum mismatch: %s" % name)
    return problems


def _user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return ""
