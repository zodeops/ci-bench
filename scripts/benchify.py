#!/usr/bin/env python3
"""Make an upstream workflow benchable with the two allowed edits.

  benchify.py <workflow.yml>

1. The top-level `on:` block becomes workflow_dispatch with a `runner` input.
2. Every `runs-on:` value becomes ${{ inputs.runner }}.

Everything else in the file is left byte for byte. Text edits, not a YAML
round trip, so comments, anchors and quoting stay as upstream wrote them.
"""
import re
import sys

ON_KEYS = re.compile(r"""^(on|"on"|'on'|true)\s*:""")
TOP_KEY = re.compile(r"^[^\s#]")
RUNS_ON = re.compile(r"^(\s*-?\s*)runs-on\s*:\s*(.*)$")

DISPATCH = """on:
  workflow_dispatch:
    inputs:
      runner:
        description: runs-on label for every job
        default: ubuntu-latest

"""


def benchify(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out, i, saw_on, runs_on = [], 0, False, 0
    while i < len(lines):
        line = lines[i]
        if not saw_on and ON_KEYS.match(line):
            saw_on = True
            i += 1
            # skip the block: indented, blank or comment lines
            while i < len(lines) and not TOP_KEY.match(lines[i]):
                i += 1
            out.append(DISPATCH)
            continue
        m = RUNS_ON.match(line)
        if m:
            runs_on += 1
            indent = len(line) - len(line.lstrip(" -"))
            out.append(m.group(1) + "runs-on: ${{ inputs.runner }}\n")
            i += 1
            if m.group(2).strip() in ("", "|", ">"):
                # a block value (list or group form): drop its lines
                while i < len(lines) and (not lines[i].strip() or
                                          len(lines[i]) - len(lines[i].lstrip(" ")) > indent):
                    i += 1
            continue
        out.append(line)
        i += 1
    if not saw_on:
        raise SystemExit("no top-level on: block")
    if runs_on == 0:
        raise SystemExit("no runs-on found")
    return "".join(out)


if __name__ == "__main__":
    path = sys.argv[1]
    with open(path) as f:
        text = f.read()
    with open(path, "w") as f:
        f.write(benchify(text))
