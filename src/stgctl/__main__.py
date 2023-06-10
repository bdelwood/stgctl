"""Command-line interface."""
import click


@click.command()
@click.version_option()
def main() -> None:
    """stage-control."""


if __name__ == "__main__":
    main(prog_name="stgctl")  # pragma: no cover
