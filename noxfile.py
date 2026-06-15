"""Nox sessions."""

import os
import shutil
from pathlib import Path

import nox

package = "stgctl"
python_versions = ["3.11", "3.12"]
nox.needs_version = ">= 2024.3.2"
nox.options.sessions = (
    "pre-commit",
    "lint",
    "tests",
    "xdoctest",
)
nox.options.default_venv_backend = "uv"


def install_with_dev(session: nox.Session) -> None:
    """Install the package and dev dependency group."""
    session.install(".", "--group", "dev")


@nox.session(name="pre-commit", python=python_versions[0])
def precommit(session: nox.Session) -> None:
    """Lint using pre-commit."""
    args = session.posargs or [
        "run",
        "--all-files",
        "--hook-stage=manual",
        "--show-diff-on-failure",
    ]
    session.install("pre-commit")
    session.run("pre-commit", *args)


@nox.session(python=python_versions[0])
def lint(session: nox.Session) -> None:
    """Format & lint using ruff."""
    session.install("ruff")
    session.run("ruff", "check", "src/", "tests/")
    session.run("ruff", "format", "--check", "src/", "tests/")


@nox.session(python=python_versions[0])
def typecheck(session: nox.Session) -> None:
    """Type-check using pyrefly."""
    install_with_dev(session)
    session.run("pyrefly", "check")


@nox.session(python=python_versions)
def tests(session: nox.Session) -> None:
    """Run the test suite."""
    install_with_dev(session)
    session.run("coverage", "run", "--parallel", "-m", "pytest", *session.posargs)


@nox.session(python=python_versions[0])
def coverage(session: nox.Session) -> None:
    """Produce the coverage report."""
    args = session.posargs or ["report"]
    session.install("coverage[toml]")

    if not session.posargs and any(Path().glob(".coverage.*")):
        session.run("coverage", "combine")

    session.run("coverage", *args)


@nox.session(python=python_versions)
def xdoctest(session: nox.Session) -> None:
    """Run examples with xdoctest."""
    if session.posargs:
        args = [package, *session.posargs]
    else:
        args = [f"--modname={package}", "--command=all"]
        if "FORCE_COLOR" in os.environ:
            args.append("--colored=1")

    install_with_dev(session)
    session.run("python", "-m", "xdoctest", *args)


@nox.session(name="docs-build", python=python_versions[0])
def docs_build(session: nox.Session) -> None:
    """Build the documentation."""
    args = session.posargs or ["docs", "docs/_build"]
    if not session.posargs and "FORCE_COLOR" in os.environ:
        args.insert(0, "--color")

    install_with_dev(session)

    build_dir = Path("docs", "_build")
    if build_dir.exists():
        shutil.rmtree(build_dir)

    session.run("sphinx-build", *args)


@nox.session(name="docs", python=python_versions[0])
def docs(session: nox.Session) -> None:
    """Build and serve the documentation with live reloading."""
    install_with_dev(session)
    session.install("sphinx-autobuild")

    build_dir = Path("docs", "_build")
    if build_dir.exists():
        shutil.rmtree(build_dir)

    args = session.posargs or ["--open-browser", "docs", "docs/_build"]
    session.run("sphinx-autobuild", *args)
