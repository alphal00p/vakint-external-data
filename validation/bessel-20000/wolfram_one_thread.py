#!/usr/bin/env python3
"""Launch an existing licensed Wolfram kernel with one-thread runtime controls.

Set RUSTFLOW_WOLFRAM_KERNEL to its executable path, then use the usual
``-script FILE [arguments...]`` invocation. No license or upstream files change.
"""

import json
import os
from pathlib import Path
import sys


def launch(arguments):
    if "-script" not in arguments:
        raise ValueError("Expected -script FILE [arguments...]")
    position = arguments.index("-script")
    if position + 1 >= len(arguments):
        raise ValueError("Missing filename after -script")
    script = Path(arguments[position + 1]).absolute()
    if not script.is_file():
        raise ValueError(f"Script does not exist: {script}")
    configured = os.environ.get("RUSTFLOW_WOLFRAM_KERNEL")
    if not configured:
        raise ValueError("Set RUSTFLOW_WOLFRAM_KERNEL to an existing licensed launcher")
    # Preserve symlinks/wrappers whose behavior depends on their invocation path.
    kernel = Path(configured).absolute()
    if not kernel.is_file() or not os.access(kernel, os.X_OK):
        raise ValueError(f"Kernel launcher is not executable: {kernel}")
    if kernel.samefile(Path(__file__)):
        raise ValueError("RUSTFLOW_WOLFRAM_KERNEL must not name this wrapper")
    loader = Path(__file__).with_suffix(".wl").absolute()
    if not loader.is_file():
        raise ValueError(f"Runtime loader does not exist: {loader}")
    os.environ["RUSTFLOW_WOLFRAM_SCRIPT"] = str(script)
    os.environ["RUSTFLOW_WOLFRAM_SCRIPT_ARGUMENTS"] = json.dumps(
        arguments[position + 2:], ensure_ascii=True
    )
    command = list(arguments)
    command[position + 1] = str(loader)
    os.execv(str(kernel), [str(kernel), *command])


def main():
    try:
        launch(sys.argv[1:])
    except (OSError, ValueError) as error:
        print(f"Wolfram launcher: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
