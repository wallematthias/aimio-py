#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <string>

namespace py = pybind11;

// If AimIO headers are available (when the AimIO submodule is added), include them.
#include "AimIO/AimIO.h"

static py::dict aimfile_to_dict(const AimIO::AimFile &af) {
    py::dict d;
    d["filename"] = af.filename;
    d["version"] = static_cast<int>(af.version);
    d["id"] = af.id;
    d["reference"] = af.reference;
    d["aim_type"] = static_cast<int>(af.aim_type);
    d["buffer_type"] = static_cast<int>(af.buffer_type);
    d["position"] = py::make_tuple(af.position[0], af.position[1], af.position[2]);
    d["dimensions"] = py::make_tuple(af.dimensions[0], af.dimensions[1], af.dimensions[2]);
    d["offset"] = py::make_tuple(af.offset[0], af.offset[1], af.offset[2]);
    d["element_size"] = py::make_tuple(af.element_size[0], af.element_size[1], af.element_size[2]);
    d["processing_log"] = af.processing_log;
    d["byte_offset"] = af.byte_offset;
    return d;
}

PYBIND11_MODULE(_aimio, m) {
    m.doc() = "AimIO C++ bindings: read_aim(path) -> (ndarray, meta), write_aim(path, array, meta), aim_info(path) -> meta";

    m.def("aim_info", [](const std::string &path) {
        AimIO::AimFile af(path.c_str());
        af.ReadImageInfo();
        return aimfile_to_dict(af);
    }, py::arg("path"));

    m.def("read_aim", [](const std::string &path) {
        AimIO::AimFile af(path.c_str());
        af.ReadImageInfo();

        int nx = af.dimensions[0];
        int ny = af.dimensions[1];
        int nz = af.dimensions[2];
        size_t n = static_cast<size_t>(nx) * ny * nz;

        if (af.buffer_type == AimIO::AimFile::AIMFILE_TYPE_CHAR) {
            std::vector<int8_t> buf(n);
            af.ReadImageData(reinterpret_cast<char*>(buf.data()), n);
            // numpy shape (z,y,x)
            py::array_t<int8_t> arr({nz, ny, nx}, {static_cast<size_t>(ny*nx), static_cast<size_t>(nx), sizeof(int8_t)}, buf.data());
            // need to copy since buf will be freed
            return py::make_tuple(py::array(arr), aimfile_to_dict(af));
        } else if (af.buffer_type == AimIO::AimFile::AIMFILE_TYPE_SHORT) {
            std::vector<int16_t> buf(n);
            af.ReadImageData(buf.data(), n);
            py::array_t<int16_t> arr({nz, ny, nx}, {static_cast<size_t>(ny*nx)*sizeof(int16_t), static_cast<size_t>(nx)*sizeof(int16_t), sizeof(int16_t)}, buf.data());
            return py::make_tuple(py::array(arr), aimfile_to_dict(af));
        } else if (af.buffer_type == AimIO::AimFile::AIMFILE_TYPE_FLOAT) {
            std::vector<float> buf(n);
            af.ReadImageData(buf.data(), n);
            py::array_t<float> arr({nz, ny, nx}, {static_cast<size_t>(ny*nx)*sizeof(float), static_cast<size_t>(nx)*sizeof(float), sizeof(float)}, buf.data());
            return py::make_tuple(py::array(arr), aimfile_to_dict(af));
        } else {
            throw std::runtime_error("Unsupported buffer type in AIM file");
        }
    }, py::arg("path"));

    m.def("write_aim", [](const std::string &path, py::buffer b, py::dict meta) {
        // Acquire buffer info
        py::buffer_info info = b.request();
        if (info.ndim != 3) throw std::runtime_error("Expected 3D array (z,y,x)");

        int nz = static_cast<int>(info.shape[0]);
        int ny = static_cast<int>(info.shape[1]);
        int nx = static_cast<int>(info.shape[2]);
        size_t n = static_cast<size_t>(nx) * ny * nz;

        AimIO::AimFile af;
        af.filename = path;
        af.dimensions[0] = nx;
        af.dimensions[1] = ny;
        af.dimensions[2] = nz;

        // optional metadata
        if (meta.contains("element_size")) {
            auto es = meta["element_size"].cast<std::vector<double>>();
            af.element_size[0] = es[0]; af.element_size[1] = es[1]; af.element_size[2] = es[2];
        }
        if (meta.contains("processing_log")) {
            // ensure we set the processing log so it is written back into the AIM header
            if (py::isinstance<py::str>(meta["processing_log"])) {
                af.processing_log = meta["processing_log"].cast<std::string>();
            }
        }

        // Determine dtype and call appropriate writer
        if (info.format == py::format_descriptor<int8_t>::format()) {
            af.WriteImageData(reinterpret_cast<const char*>(info.ptr));
        } else if (info.format == py::format_descriptor<int16_t>::format()) {
            af.WriteImageData(reinterpret_cast<const short*>(info.ptr));
        } else if (info.format == py::format_descriptor<float>::format()) {
            af.WriteImageData(reinterpret_cast<const float*>(info.ptr));
        } else {
            throw std::runtime_error("Unsupported array dtype for write_aim (use int8, int16, or float32)");
        }

        return aimfile_to_dict(af);
    }, py::arg("path"), py::arg("array"), py::arg("meta") = py::dict());
}
