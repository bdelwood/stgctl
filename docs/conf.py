"""Sphinx configuration."""

project = "stage-control"
author = "Brodi Elwood"
copyright = "2023, Brodi Elwood"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "myst_parser",
    "cyclopts.ext.sphinx",
]
autodoc_typehints = "description"
html_theme = "furo"

# Generate heading anchors so the CLI reference's auto-generated
# table-of-contents links resolve.
myst_heading_anchors = 6
