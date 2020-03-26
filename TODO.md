- Rename to `flatex`
  Make functions sub-commands

- Replace `-clean` suffix with `.suffix`
  => Makes it easy to see what was performed with `Path().suffixes`.

- Add `cp-eps` and `embed-bbl` commands

- Add comment-stripping function, supported by *arxiv_latex_cleaner*.

- Support name placeholder macros of the form `\def\arnold/{Arnold Schwarzenegger}`.
- State where an error occurred:
  + parsing definitions
  + parsing tex
  + in all cases, in which file
  Using different exception types is probably the best way to do this.

- Replace constants with Enums

- Treat default arguments in Latex macros ?
