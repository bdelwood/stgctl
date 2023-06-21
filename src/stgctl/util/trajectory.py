import numpy
from stgctl.schema.models import Size


grid_size = 60
step_size = 1867


def linear_grid(
    grid_size: Size, step_size: Size
) -> tuple[numpy.ndarray, numpy.ndarray]:
    x = numpy.arange(0, grid_size.X * step_size.X, step_size.X)
    y = numpy.arange(0, grid_size.Y * step_size.Y, step_size.Y)
    return (x, y)


def path_2d_numpy(x: numpy.ndarray, y: numpy.ndarray) -> numpy.ndarray:
    coords = numpy.stack(numpy.meshgrid(x, y), axis=-1)
    coords[1::2] = coords[1::2, ::-1]
    return coords.reshape(-1, 2)


def gen_2d_trajectory(grid_size: Size, step_size: Size) -> numpy.ndarray:
    path = path_2d_numpy(*linear_grid(grid_size, step_size))
    return path
