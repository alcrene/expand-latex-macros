This package combines the functionality of two other Python packages:

  - [*FLaP*](https://pythonhosted.org/FLaP/), for flattening a hierarchy of LaTeX files.
  - [*de-macro*](https://www.ctan.org/pkg/de-macro), for replacing macros in a document by their definitions.

It is essentially a Python 3 port of the *de-macro* script; *FLaP* is simply called before launching the de-macroing routines.

----

# Quick-start instructions

  1. Place all your custom macro definitions in a file ending with
     `-private.sty`. For example, `definitions-private.sty`. &lt;br&gt;
     If you already have a `.tex` file you use for your personal macros,
     just change the extension to `.sty`. Then change how you import the file
     as described in step 2.
  2. Import your private definitions file into your .tex  with `\usepackage`.
     For example:

     ```latex
     % In file `main.tex`
     \usepackage{definitions-private}
     ```
     Keep the definitions file simple. In particular, don't use options
     when loading it (e.g. `\usepackage[smile]{definitions-private}`).
  3. Run this script on the tex file:

    ```bash
    expand_latex_macros main.tex outputdir
    ```

    Just like when compiling with LaTeX, your `*-private.sty` file must be
    findable from the directory where the command is *executed*.

# Limitations

  - Commands with default arguments are not supported.
    They cannot even be present in your definitions file, even if you don't use
    them. Probably best to avoid any kind of special logic.
  - Only put recognized commands recognized in your definitions file,
    specifically:

      - newcommand
      - renewcommand
      - newenvironment
      - renewenvironment

    In particular, name placeholder macros of the style
    `\def\arnold/{Arnold Schwarzenegger}` (arguably a
    [canonical idiom](https://tex.stackexchange.com/a/290504)) are not supported.
  - The definitions file is *removed* from the merged document, so any
    definitions left therein are lost.

# Other considerations

## Removing comments

To remove comments automatically, you can use the [arxiv_latex_cleaner](https://github.com/google-research/arxiv-latex-cleaner/)
script, before launching *expand-latex-macros*.

---

   Copyright 2020 Alexandre René

   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see <https://www.gnu.org/licenses/>.

---
# Original *de-macro* readme


Original copyright notice:<br>
  Copyright 2005 Péter Gács<br>
  Licensed under the Academic Free Licence version 2.1

                          DE-MACRO

Version 1.3 - this version is much more conservative about deleting
              comments and inserting or deleting blank space: tries to
              leave in all comments, adds space only when necessary, and
              tries not to delete space in the main text.
              The motivating comments came from Daniel Webb.
Version 1.2 - a syntactical bug corrected, thanks Brian de Alwis!


PURPOSE

This program can eliminate most private macros from a LaTeX file.
Applications:
  - your publisher has difficulty dealing with many private macros
  - you cooperate with colleagues who do not understand your macros
  - preprocessing before a system like latex2html, which is somewhat
    unpredictable with private macros.

PLATFORM

This is a Python program, which I only have tried to run under Unix.  But
the Unix dependence is minimal (for example all the directory path
references are platform-independent).  It should be easy to adapt the
program to Windows, and also to avoid command-line arguments.

In case your Python is not in /usr/bin, you should change the
top line (the "shebang" line) of the program accordingly.
This top line uses the -O option for python (stands for "optimize").
Without it, the program may run too slowly.  If you do not care for speed,
a number of other complications (the database, the checking for newer
versions) could be eliminated.

USAGE

Command line:

de-macro [--defs &lt;defs-db&gt;] &lt;tex-file-1&gt;[.tex] [&lt;tex-file-2&gt;[.tex] ...]

Simplest example:    de-macro testament

(As you see, the &lt;&gt; is used only in the notation of this documentation,
you do should not type it.)

If &lt;tex-file-i&gt; contains a command \usepackage{&lt;defs-file&gt;-private}
then the file &lt;defs-file&gt;-private.sty will be read, and its macros will be
replaced  in &lt;tex-file-i&gt; with their definitions.
The result is in &lt;tex-file-i&gt;-clean.tex.

Only newcommand, renewcommand, newenvironment, and renewenvironment are
understood (it does not matter, whether you write new or renew).
These can be nested but do not be too clever, since I do not
guarantee the same expansion order as in TeX.

FILES

&lt;tex-file-1&gt;.db
&lt;tex-file&gt;-clean.tex
&lt;defs-file&gt;-private.sty

For speed, a macro database file called &lt;defs-file&gt;.db is created.
If such a file exists already then it is used.
If &lt;defs-file&gt;-private.sty is older than &lt;tex-file-1&gt;.db then it will not
be used.

It is possible to specify another database filename via --defs &lt;defs-db&gt;.
Then &lt;defs-db&gt;.db will be used.

(Warning: with some Python versions and/or Unix platforms, the database
file name conventions may be different from what is said here.)

For each &lt;tex-file-i&gt;, a file &lt;tex-file-i&gt;-clean.tex will be produced.
If &lt;tex-file-i&gt;-clean.tex is newer than &lt;tex-file-i&gt;.tex then it stays.

INPUT COMMAND

If a tex file contains a command \input{&lt;tex-file-j&gt;} or \input &lt;tex-file-j&gt;
then &lt;tex-file-j&gt;.tex is processed recursively, and &lt;tex-file-j&gt;-clean.tex
will be inserted into the final output.
For speed, if &lt;tex-file-j&gt;-clean.tex is newer than &lt;tex-file-j&gt;.tex
then &lt;tex-file-j&gt;.tex will not be reprocessed.

The dependency checking is not sophisticated, so if you rewrite some macros
then remove all *-clean.tex files!
