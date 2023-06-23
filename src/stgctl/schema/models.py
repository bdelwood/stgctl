from collections.abc import Iterator
from dataclasses import dataclass


@dataclass
class Size:
    X: int
    Y: int

    def __post_init__(self) -> None:
        self.X = int(round(self.X))
        self.Y = int(round(self.Y))

    def __iter__(self) -> Iterator[int]:
        yield self.X
        yield self.Y

    def __len__(self) -> int:
        return 2
