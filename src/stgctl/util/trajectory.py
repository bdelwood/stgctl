"""Functions for generating a 2D trajectory."""

import numpy
from stgctl.schema.models import Size


grid_size = 60
step_size = 1867


def linear_grid(
    grid_size: Size, step_size: Size
) -> tuple[numpy.ndarray, numpy.ndarray]:
    """Create a 2D grid of points grid_size.X * grid_size.Y.

    Args:
        grid_size (Size): number of raster points in (x,y)
        step_size (Size): steps between raster points (x,y)

    Returns:
        tuple[numpy.ndarray, numpy.ndarray]: tuple where first elem is x raster points,
        second is y raster points. dtype of array is int
    """
    x = numpy.linspace(0, grid_size.X * step_size.X, grid_size.X)
    y = numpy.linspace(0, grid_size.Y * step_size.Y, grid_size.Y)
    return (x.round().astype(int), y.round().astype(int))


def path_2d_numpy(x: numpy.ndarray, y: numpy.ndarray) -> numpy.ndarray:
    """Take a nonordered grid of points and order them in a back-and-forth raster.

    Args:
        x (numpy.ndarray): grid x coordinates
        y (numpy.ndarray): grid y coordinates

    Returns:
        numpy.ndarray: Array of coordinates ordered in a back-and-forth raster.
        One can think of this result as the parametric function (X(t), Y(t)),
        where the row index is "time".
    """
    coords = numpy.stack(numpy.meshgrid(x, y), axis=-1)
    coords[1::2] = coords[1::2, ::-1]
    return coords.reshape(-1, 2)


def gen_2d_trajectory(grid_size: Size, step_size: Size) -> numpy.ndarray:
    """Helper function to generate a 2D grid and form a back-and-forth raster.

    Args:
        grid_size (Size): number of raster points in (x,y)
        step_size (Size): steps between raster points (x,y)

    Returns:
        numpy.ndarray: Array of coordinates ordered in a back-and-forth raster.
        One can think of this result as the parametric function (X(t), Y(t)),
        where the row index is "time".
    """
    path = path_2d_numpy(*linear_grid(grid_size, step_size))
    return path
