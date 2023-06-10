"""Sphinx configuration."""
project = "stage-control"
author = "Brodi Elwood"
copyright = "2023, Brodi Elwood"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_click",
    "myst_parser",
]
autodoc_typehints = "description"
html_theme = "furo"
