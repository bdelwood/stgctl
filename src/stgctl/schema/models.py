"""Models for stgctl."""

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass
class Size:
    """Dataclass for holing index size in two dimensions, X and Y.

    Attributes:
        X (int): The index size in the X dimension.
        Y (int): The index size in the Y dimension.
    """

    X: int
    Y: int

    def __post_init__(self) -> None:
        """A method that runs after the instance has been initialized.

        Rounds the initial values for X and Y to the nearest integer.
        """
        self.X = int(round(self.X))
        self.Y = int(round(self.Y))

    def __iter__(self) -> Iterator[int]:
        """Always iterate X then Y."""
        yield self.X
        yield self.Y

    def __len__(self) -> int:
        """Size is always of length 2.

        Returns:
            int: length of Size
        """
        return 2
