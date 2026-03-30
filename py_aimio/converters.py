"""Image converters between AIM and SimpleITK representations."""

import os
import warnings

import numpy as np

from .calibration import (
    get_aim_calibration_constants_from_processing_log,
    get_aim_hu_equation,
)
def aim_to_sitk(file_path, scaling, write_mha=False):
    """Read AIM and return a SimpleITK image, optionally converted to another unit."""
    import SimpleITK as sitk
    import vtkbone
    from .vtk_utils import vtkImageData_to_numpy

    reader = vtkbone.vtkboneAIMReader()
    reader.DataOnCellsOff()
    reader.SetFileName(file_path)
    reader.Update()
    img_file = reader.GetOutput()
    img_log = reader.GetProcessingLog()

    np_image = vtkImageData_to_numpy(img_file)

    if scaling == "mu":
        mu_scaling, _, _, _, _ = get_aim_calibration_constants_from_processing_log(img_log)
        np_image_scaled = np_image / mu_scaling
    elif scaling == "HU":
        m, b = get_aim_hu_equation(img_log)
        np_image_scaled = (np_image * m) + b
    elif scaling == "BMD":
        mu_scaling, _, _, density_slope, density_intercept = get_aim_calibration_constants_from_processing_log(img_log)
        np_image_scaled = np_image / mu_scaling * density_slope + density_intercept
    elif scaling in ("binary", "none"):
        np_image_scaled = np_image
    else:
        raise ValueError(f"{scaling} is not a valid scaling option. Enter with 'HU', 'mu', 'BMD', 'binary' or 'none'")

    origin = np.asarray(img_file.GetOrigin())
    spacing = np.asarray(img_file.GetSpacing())
    np_image_scaled = np.transpose(np_image_scaled)

    sitk_img = sitk.GetImageFromArray(np_image_scaled)
    sitk_img.SetOrigin(origin)
    sitk_img.SetSpacing(spacing)
    sitk_img.SetMetaData("processing_log", img_log.replace("\n", "_LINEBREAK_"))
    sitk_img.SetMetaData("unit", scaling if scaling != "none" else "native")

    if write_mha:
        folder = os.path.dirname(file_path)
        file = os.path.basename(file_path).split(".")[0]
        out_path = os.path.join(folder, f"{file}.mha")
        sitk.WriteImage(sitk_img, out_path)

    return sitk_img


def sitk_to_aim(file_path="", sitk_img=None, write_aim=False, output_path=""):
    """Convert a SimpleITK image to vtkImageData suitable for AIM writing."""
    import SimpleITK as sitk
    import vtk
    import vtkbone
    from .vtk_utils import numpy_to_vtkImageData

    if file_path == "" and sitk_img is None:
        raise ValueError("You have to specify either a SimpleITK image or a file path")
    if file_path != "":
        sitk_img = sitk.ReadImage(file_path)

    keys = sitk_img.GetMetaDataKeys()
    if "processing_log" not in keys:
        raise ValueError("No header information present in SimpleITK image")
    if "unit" not in keys:
        warnings.warn("No unit specified for SimpleITK, assuming native units.", stacklevel=2)
        unit = "native"
    else:
        unit = sitk_img.GetMetaData("unit")

    img_log = sitk_img.GetMetaData("processing_log").replace("_LINEBREAK_", "\n")
    np_image = sitk.GetArrayFromImage(sitk_img)

    vtktype = vtk.VTK_SHORT
    if unit == "mu":
        mu_scaling, _, _, _, _ = get_aim_calibration_constants_from_processing_log(img_log)
        np_image_native = np_image * mu_scaling
    elif unit == "HU":
        m, b = get_aim_hu_equation(img_log)
        np_image_native = (np_image - b) / m
    elif unit == "BMD":
        mu_scaling, _, _, density_slope, density_intercept = get_aim_calibration_constants_from_processing_log(img_log)
        np_image_native = (np_image - density_intercept) * mu_scaling / density_slope
    elif unit == "binary":
        np_image_native = np_image
        vtktype = vtk.VTK_CHAR
    elif unit == "native":
        np_image_native = np_image
    else:
        raise ValueError(f"Incorrect image unit specified in metadata: {unit}.")

    np_image_native = np.transpose(np_image_native)
    origin = sitk_img.GetOrigin()
    spacing = sitk_img.GetSpacing()

    vtk_img = numpy_to_vtkImageData(np_image_native, spacing=spacing, origin=origin, array_type=vtktype)

    if write_aim:
        if file_path == "" and output_path == "":
            raise ValueError("No output path is given to write AIM file")
        if output_path == "":
            folder = os.path.dirname(file_path)
            file = os.path.basename(file_path).split(".")[0]
            output_path = os.path.join(folder, f"{file}.aim")

        writer = vtkbone.vtkboneAIMWriter()
        writer.SetFileName(output_path)
        writer.SetInputData(vtk_img)
        writer.NewProcessingLogOff()
        writer.SetProcessingLog(img_log)
        writer.Update()
        writer.Write()

    return vtk_img
