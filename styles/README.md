# CSL style files

Drop official Citation Style Language files here (e.g. `apa.csl`,
`chicago-author-date.csl`, `modern-language-association.csl`) to get full
citation fidelity. Get them from https://github.com/citation-style-language/styles
(or `pip install citeproc-py-styles`, which the renderer also checks).

The filename stem is the style id shown in the app's dropdown — e.g. `apa.csl`
appears as `apa`.

If no `.csl` file (and no `citeproc-py-styles`) is found for the chosen style,
the app falls back to a built-in author-date formatter so it still produces a
usable bibliography offline.
