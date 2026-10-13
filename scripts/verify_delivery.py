#!/usr/bin/env python3
"""Verify delivered folders against their checksums.sha256.

    python verify_delivery.py /deliveries/STRM/EP_1/STRM_E1_0010/v003 [more folders]

Exit code 0 when every folder matches, 1 otherwise.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "manifest", os.path.join(HERE, os.pardir, "python", "app", "manifest.py"))
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)


def main(folders):
    if not folders:
        print(__doc__)
        return 2
    bad = 0
    for folder in folders:
        problems = manifest.verify_folder(folder)
        if problems:
            bad += 1
            print("FAIL %s" % folder)
            for p in problems:
                print("   %s" % p)
        else:
            print("OK   %s" % folder)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
