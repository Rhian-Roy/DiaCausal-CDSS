#!/usr/bin/env python3
"""
Execute a notebook's code cells without starting a Jupyter kernel.

    python verify_notebook.py                                  # check only
    python verify_notebook.py --write                           # check + save outputs
    python verify_notebook.py other.ipynb --write

Why this exists. `jupyter nbconvert --execute` is the right tool and is what the
team should run on a normal machine. But it has to bind a local socket to talk to
the kernel, and in a sandboxed environment that is refused outright:

    PermissionError: [Errno 1] Operation not permitted   (tmp_sock.bind)

So this runs the cells the way a kernel would — in order, in one shared
namespace — and reports the first failure with its cell number and its source. It
verifies the two things that actually matter: no cell raises, and every cell can
see the names bound by the cells above it.

With `--write` it also records what each cell produced back into the .ipynb:
stdout as stream output, `display()` calls as HTML tables, and matplotlib figures
as embedded PNGs. That makes the notebook readable on GitHub, or in a report
appendix, without anyone having to run it first.

Two behaviours it shims, because they exist in IPython and not in plain Python:

    display(obj)      -> recorded as an output (HTML for DataFrames)
    bare last line    -> IPython echoes the value; here it is evaluated and
                         recorded, so a cell ending in `df.head()` is still
                         exercised rather than silently skipped
"""

from __future__ import annotations

import argparse
import ast
import base64
import io
import os
import sys
import time
import traceback

os.environ.setdefault("MPLCONFIGDIR", os.environ.get("TMPDIR", "/tmp"))

import matplotlib
matplotlib.use("Agg")          # no display in a headless run
import matplotlib.pyplot as plt

import nbformat
from nbformat.v4 import new_output


class Recorder:
    """Collects a cell's outputs in the order they were produced.

    Text is buffered rather than emitted per `write()` call, because a single
    `print` produces two writes (the text, then the newline) and one stream
    output per write would bloat the notebook enormously.
    """

    def __init__(self) -> None:
        self.outputs: list = []
        self._text: list[str] = []

    # -- file-like, so it can stand in for sys.stdout ------------------------
    def write(self, s: str) -> int:
        self._text.append(s)
        return len(s)

    def flush(self) -> None:
        pass

    # -- ordered recording --------------------------------------------------
    def _flush_text(self) -> None:
        if not self._text:
            return
        text, self._text = "".join(self._text), []
        if text.strip():
            self.outputs.append(new_output("stream", name="stdout", text=text))

    def add_data(self, data: dict) -> None:
        self._flush_text()      # keep interleaving faithful
        self.outputs.append(new_output("display_data", data=data, metadata={}))

    def finish(self) -> list:
        self._flush_text()
        return self.outputs


def as_mime(obj) -> dict:
    """Bundle one object into a MIME dict the way IPython's formatters would."""
    try:
        import pandas as pd
        if isinstance(obj, pd.DataFrame):
            return {"text/html": obj.to_html(max_rows=60, border=0),
                    "text/plain": obj.to_string()}
        if isinstance(obj, pd.Series):
            return {"text/plain": obj.to_string()}
    except Exception:
        pass
    return {"text/plain": repr(obj)}


def capture_figures(rec: Recorder) -> None:
    """Embed every open matplotlib figure as a PNG, then close it."""
    for num in plt.get_fignums():
        fig = plt.figure(num)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        rec.add_data({"image/png": base64.b64encode(buf.getvalue()).decode("ascii")})
        plt.close(fig)


def make_namespace(rec: Recorder) -> dict:
    """A namespace that behaves enough like IPython's for these cells."""

    def display(*objs):
        for obj in objs:
            rec.add_data(as_mime(obj))

    def show(*_args, **_kwargs):
        # Cells call plt.show() mid-cell. Capturing here rather than at the end
        # of the cell is what keeps figures in the right place relative to the
        # text printed around them.
        capture_figures(rec)

    plt.show = show                       # patched for the whole run
    return {"__name__": "__main__", "display": display}


def run_cell(source: str, ns: dict) -> None:
    """Exec a cell, then evaluate-and-record a trailing bare expression."""
    tree = ast.parse(source, mode="exec")
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        head, tail = tree.body[:-1], tree.body[-1]
        exec(compile(ast.Module(body=head, type_ignores=[]), "<cell>", "exec"), ns)
        value = eval(compile(ast.Expression(body=tail.value), "<cell>", "eval"), ns)
        if value is not None:
            ns["display"](value)
    else:
        exec(compile(tree, "<cell>", "exec"), ns)


def main(path: str, write: bool) -> int:
    nb = nbformat.read(path, as_version=4)
    code_cells = [(i, c) for i, c in enumerate(nb.cells, 1) if c.cell_type == "code"]

    rec = Recorder()
    ns = make_namespace(rec)
    real_stdout = sys.stdout

    print(f"verifying {path} — {len(code_cells)} code cells"
          f"{'  (writing outputs)' if write else ''}\n" + "─" * 72,
          file=real_stdout)
    t_all = time.time()

    for n, (index, cell) in enumerate(code_cells, 1):
        first = next((l for l in cell.source.splitlines() if l.strip()), "")
        t0 = time.time()
        rec.outputs, rec._text = [], []

        sys.stdout = rec
        try:
            run_cell(cell.source, ns)
            capture_figures(rec)          # anything not already shown
        except Exception:
            sys.stdout = real_stdout
            print(f"\n{'─' * 72}\nFAILED at code cell {n} (notebook cell {index})\n")
            print(cell.source)
            print("─" * 72)
            # stdout, not stderr: when this is piped, interleaving the two
            # streams puts the traceback somewhere unhelpful.
            traceback.print_exc(file=sys.stdout)
            return 1
        finally:
            sys.stdout = real_stdout

        outputs = rec.finish()
        if write:
            cell.outputs = outputs
            cell.execution_count = n

        n_img = sum(1 for o in outputs if "image/png" in o.get("data", {}))
        badge = f"  [{n_img} figure{'s' if n_img != 1 else ''}]" if n_img else ""
        print(f"  cell {n:>2}/{len(code_cells)}  {time.time()-t0:6.1f}s   "
              f"{first.strip()[:52]}{badge}", file=real_stdout)

    print("─" * 72, file=real_stdout)
    print(f"ALL {len(code_cells)} CODE CELLS PASSED in {time.time()-t_all:.1f}s",
          file=real_stdout)

    if write:
        nbformat.write(nb, path)
        print(f"outputs written into {path}", file=real_stdout)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("notebook", nargs="?", default="01_Causal_Inference_Basics.ipynb")
    ap.add_argument("--write", action="store_true",
                    help="save captured outputs back into the notebook")
    a = ap.parse_args()
    sys.exit(main(a.notebook, a.write))
