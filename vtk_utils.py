"""VTK/Numpy conversion utilities."""

import numpy as np
import vtk
from vtk.util.numpy_support import numpy_to_vtk, vtk_to_numpy


def numpy_to_vtkImageData(array, spacing=None, origin=None, array_type=vtk.VTK_FLOAT):
    """Convert a numpy array to vtkImageData."""
    if spacing is None:
        spacing = np.ones_like(array.shape)
    if origin is None:
        origin = np.zeros_like(array.shape)

    temp = np.ascontiguousarray(np.atleast_3d(array))
    image = vtk.vtkImageData()
    vtkArray = numpy_to_vtk(temp.ravel(order="F"), deep=True, array_type=array_type)
    image.SetDimensions(array.shape)
    image.SetSpacing(spacing)
    image.SetOrigin(origin)
    image.GetPointData().SetScalars(vtkArray)
    return image


def vtkImageData_to_numpy(image):
    """Convert vtkImageData to a numpy array."""
    array = vtk_to_numpy(image.GetPointData().GetScalars())
    return array.reshape(image.GetDimensions(), order="F")
