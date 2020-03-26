from warnings import warn
import os
import shutil
import click

"""
Script assumes figures are exactly one directory deep.
E.g. under 'figures', not 'figures/eps'
"""

@click.command()
@click.argument('flatdir', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.argument('figdir', type=click.Path(exists=True, file_okay=False, dir_okay=True))
def main(flatdir, figdir):
    figprefix = os.path.basename(figdir)
    for filename in os.listdir(flatdir):
        if filename.startswith(figprefix+'_'):
            targetfilename = os.path.splitext(filename)[0] + '.eps'
            sourcefilename = targetfilename[len(figprefix)+1:]
            sourcepathname = os.path.join(figdir, sourcefilename)
            targetpathname = os.path.join(flatdir, targetfilename)
            if os.path.exists(sourcepathname):
                shutil.copy(sourcepathname, targetpathname, follow_symlinks=True)
            else:
                warn("Missing eps file '{}'".format(sourcepathname))

if __name__ == "__main__":
    main()
