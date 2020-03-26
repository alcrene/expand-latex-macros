"""Change [name of bibtex file] as required."""

import sys

stem = sys.argv[1]  # tex filename without extension
texpath = stem + '.tex'
bblpath = stem + '.bbl'
outpath = stem + '.embedbib.tex'
with open(texpath, 'r') as infile:
    with open(outpath, 'w') as outfile:
        for line in infile:
            if r"\bibliography{[name of bibtex file]}" in line:
                with open(bblpath, 'r') as bblfile:
                    outfile.write(bblfile.read())
            else:
                outfile.write(line)
