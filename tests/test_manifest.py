import importlib.util
import json
import pathlib

import pytest

spec = importlib.util.spec_from_file_location(
    "manifest", pathlib.Path(__file__).resolve().parents[1] / "python" / "app" / "manifest.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

SHOT = {"project_code": "STRM", "sequence": "EP_1", "shot": "STRM_E1_0010",
        "version_number": 3, "first_frame": 1001, "last_frame": 1003}


def make(tmp_path, n=3, content=lambda i: b"frame%d" % i):
    src, dst = tmp_path / "pub", tmp_path / "deliver"
    src.mkdir(); dst.mkdir()
    pairs = []
    for i in range(n):
        s, d = src / ("a.%04d.exr" % (1001 + i)), dst / ("d.%04d.exr" % (1001 + i))
        s.write_bytes(content(i)); d.write_bytes(content(i))
        pairs.append((s, d))
    return dst, pairs


def test_manifest_contents(tmp_path):
    dst, pairs = make(tmp_path)
    man = m.write_manifest(dst, SHOT, pairs)
    on_disk = json.loads((dst / "STRM_E1_0010_v003_manifest.json").read_text())
    assert on_disk == man
    assert man["frame_count"] == 3 and man["version"] == 3
    assert man["total_bytes"] == sum(f["bytes"] for f in man["files"])
    assert all(len(f["sha256"]) == 64 for f in man["files"])
    assert man["files"][0]["source"].endswith("a.1001.exr")


def test_checksum_file_matches_sha256sum_format(tmp_path):
    dst, pairs = make(tmp_path)
    m.write_manifest(dst, SHOT, pairs)
    lines = (dst / "checksums.sha256").read_text().splitlines()
    assert len(lines) == 3
    h, _, name = lines[0].partition("  ")
    assert name == "d.1001.exr" and h == m.file_hash(dst / name)


def test_verify_ok_then_detects_corruption_and_missing(tmp_path):
    dst, pairs = make(tmp_path)
    m.write_manifest(dst, SHOT, pairs)
    assert m.verify_folder(dst) == []
    (dst / "d.1002.exr").write_bytes(b"tampered")
    (dst / "d.1003.exr").unlink()
    problems = m.verify_folder(dst)
    assert "checksum mismatch: d.1002.exr" in problems and "missing: d.1003.exr" in problems


def test_verify_without_checksum_file(tmp_path):
    assert m.verify_folder(tmp_path) == ["checksums.sha256 not found"]


def test_md5_manifest_has_no_sha_file(tmp_path):
    dst, pairs = make(tmp_path)
    man = m.write_manifest(dst, SHOT, pairs, "md5")
    assert "md5" in man["files"][0] and not (dst / "checksums.sha256").exists()


def test_none_skips_hashing(tmp_path):
    dst, pairs = make(tmp_path)
    man = m.write_manifest(dst, SHOT, pairs, "none")
    assert "sha256" not in man["files"][0] and "md5" not in man["files"][0]


def test_unknown_algorithm_rejected(tmp_path):
    dst, pairs = make(tmp_path)
    with pytest.raises(ValueError):
        m.write_manifest(dst, SHOT, pairs, "crc32")
    assert not list(dst.glob("*manifest.json"))


def test_large_file_hashes_in_chunks(tmp_path):
    p = tmp_path / "big.bin"
    p.write_bytes(b"x" * (m.CHUNK + 5))
    import hashlib
    assert m.file_hash(p) == hashlib.sha256(b"x" * (m.CHUNK + 5)).hexdigest()
