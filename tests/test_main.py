import os
from os import path
# from pathlib import Path
from click.testing import CliRunner

import expand_latex_macros as elm

here = path.abspath(path.dirname(__file__))
os.chdir(here)

# flap command

def expand_and_compare(prefix="complex"):
    runner = CliRunner()
    # Latex must be compiled from within source directory
    os.chdir(f"{prefix}-latex-src")
    result = runner.invoke(elm.main, ("main.tex",
                                      f"../{prefix}-latex-expanded"),
                           catch_exceptions=False)
    os.chdir("..")

    # with open(here/"latex-src/main.tex", 'r') as src:
    #     expanded_tex = src.read()
    # with open("latex-expanded/main-expanded.tex", 'w') as out:
    #     out.write(expanded_tex)
    with open(f"{prefix}-latex-expanded/merged-clean.tex", 'r') as expanded:
        with open(f"{prefix}-latex-target/merged-clean.tex", 'r') as target:
            for lineno, (line_expanded, line_target) \
                  in enumerate(zip(expanded, target), start=1):
                assert line_expanded == line_target, (
                    f"Files differ on line {lineno}:\n"
                    f"Expanded file:\n\t{line_expanded}\n"
                    f"Target file:\n\t{line_target}")

def test_simple():
    return expand_and_compare('simple')

def test_complex():
    return expand_and_compare('complex')
