"""Prevent the known mypy debt from growing while modules are tightened incrementally."""

from __future__ import annotations

import re
import subprocess
import sys


MAX_ERRORS = 120


def main() -> int:
    completed = subprocess.run(
        [sys.executable, "-m", "mypy", "app", "--no-incremental", "--show-error-codes"],
        check=False,
        capture_output=True,
        text=True,
    )
    output = completed.stdout + completed.stderr
    match = re.search(r"Found (\d+) errors? in (\d+) files?", output)
    if match is None:
        print(output, end="")
        print("mypy baseline check could not read the result", file=sys.stderr)
        return 2
    errors = int(match.group(1))
    files = int(match.group(2))
    print(f"mypy debt: {errors} errors in {files} files; allowed maximum: {MAX_ERRORS}")
    if errors > MAX_ERRORS:
        print(output, end="")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
