"""Entrypoint: forecast every case handed to this run.

The grader runs one case at a time (`python3 -P -s /bot/main.py`), with that
case's file alone in the input directory, and reads the matching output file.
Every case in the input directory is processed in name order, so two runs on the
same input write byte-identical output.
"""

import json
import os
import sys
from pathlib import Path

# The grader's -P leaves this directory off sys.path; put it back first so the
# model module shipped beside this file is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import model

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = model.forecast(case)
        # Never leave a case without a file: an unwritten case is scored as invalid
        # and voids the whole entry.
        text = json.dumps(forecast, separators=(",", ":")) + "\n"
        (OUTPUT_DIR / (path.stem + ".out")).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
