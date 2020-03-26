#! /bin/sh

# Lines starting with >>>> need to be edited

set -e  # exit when any command fails

>>>> figprefix="NECO-10-19-3663-Figure.{}"
>>>> finalsourcename="NECO-10-19-3663-Source"
>>>> finalpdfname="NECO-10-19-3663-PDF"
>>>> finalpdftitle="NECO-10-19-3663"   # What appears in the PDF title bar
>>>> removepdffigures="no"   # Useful if you need to submit EPS figures – FLaP always copies pdfs

>>>> source "/path/to/script/environment/bin/activate"
>>>> root= "/path/to/paper/"

echo "Remove previously flattened files..."
rm -rf "$root/flat-latex"/*

# Remove comments from sources
echo "Removing comments from sources..."
>>>> arxiv_latex_cleaner "$root/subdir"  # Creates meso_inference_arXiv directory
# Copy the .bib file arxiv_latex_cleaner forgot
>>>> cp "$root/subdir/bibliography.bib" "$root/subdir_arXiv/bibliography.bib"

# Combine all source files and expand macros
echo "Combining source files and expanding macros..."
>>>> cd "$root/subdir_arXiv"
# Don't rename figures - we need to copy .eps files first
expand-latex-macros --renamefigs="" main.tex "$root/flat-latex"
# Remove the temporary directory created by arxiv_latex_cleaner
cd "$root"
>>>> rm -r "$root/subdir_arXiv"

# Manage EPS figures
# Copy the .eps files (flat-latex only copies .pdf figures)
echo "Copying .eps files into flattened directory..."
>>>> python "$root/cp_eps_files.py" "$root/flat-latex" "$root/subdir/figures"
cd "$root/flat-latex"
# Convert the .eps files to CMYK
echo "Converting .eps files to CMYK..."
convert-to-cmyk --format eps --in-place "$root/flat-latex"

# Rename figures
echo "Renaming figures to the journal's format..."
rename-figures --renamestr="$figprefix" --start=1 --figexts="eps" "$root/flat-latex/merged-clean.tex"

# Embed bibliography
# Remove underscore from bib filename
echo "Removing underscore from bibliography filename to avoid compilation error..."
# flap adds underscores to filenames in subdirs, which is illegal for the bibliography
>>>> mv folder_bibliography.bib folder-bibliography.bib
>>>> sed -i "s/\\\\bibliography{folder_bibliography}/\\\\bibliography{folder-bibliography}/g" merged-clean.renamed.tex
# Create the bbl file
echo "Compiling source with \`latex merged-clean.renamed.tex\`..."
latex merged-clean.renamed.tex
rm merged-clean.renamed.dvi
echo "Compiling references with \`bibtex merged-clean.renamed.aux\`..."
bibtex merged-clean.renamed.aux
# Embed the .bbl file into the .tex
echo "Embedding .bbl file with \`python ../substitute_bib.py \"merged-clean.renamed\"\`..."
>>>> python ../substitute_bib.py "merged-clean.renamed"

# Rename source to set the text in title bar
# (This might not actually do anything…)
mv merged-clean.renamed.embedbib.tex "$finalpdftitle.tex"

# Compile final document
# Compile thrice to ensure all refs are OK
echo "Compile 3x with \`latex $finalpdftitle.tex\`..."
latex "$finalpdftitle.tex"
latex "$finalpdftitle.tex"
latex "$finalpdftitle.tex"

dvips -Ppdf -G0 "$finalpdftitle.dvi"
ps2pdf -dPDFSETTINGS=/prepress -dEmbedAllFonts=true "$finalpdftitle.ps"

# Cleanup
echo "Renaming source to '$finalsourcename.tex'..."
mv "$finalpdftitle.tex" "$finalsourcename.tex"
echo "Renaming final pdf to '$finalpdfname.pdf'..."
mv "$finalpdftitle.pdf" "$finalpdfname.pdf"
echo "Removing intermediate files..."
rm merged*
rm -rf _cmyk
rm -f flap.log
rm -f etc-meso-inference-edited.bib
rm -f *.sty
rm -f *.dvi
rm -f *.ps
rm -f *.log
rm -f *.out
rm -f *.aux

if [ $removepdffigures == "yes" ]; then
    rm "${figprefix//\{\}}"*.pdf   # Use string manipulation to remove curly brackets
fi

# Deactivate python virtual environment
deactivate

echo "Done."
