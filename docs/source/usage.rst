Usage
=====

Install
-------

.. code-block:: bash

   pip install aimio-py

Minimal read/write example
--------------------------

.. code-block:: python

   from py_aimio import read_aim, read_isq, write_aim

   arr, meta = read_aim("scan.AIM")
   write_aim("copy.AIM", arr, meta)

   isq_arr, isq_meta = read_isq("scan.ISQ")
   isq_hu, _ = read_isq("scan.ISQ", unit="hu")
   isq_bmd, _ = read_isq("scan.ISQ", unit="density")

Metadata-only example
---------------------

.. code-block:: python

   from py_aimio import aim_info, isq_info

   info = aim_info("scan.AIM")
   print("Dimensions:", info["dimensions"])

   isq_info_dict = isq_info("scan.ISQ")
   print("ISQ dimensions:", isq_info_dict["dimensions"])

Density/HU conversion example
-----------------------------

.. code-block:: python

   from py_aimio import read_aim, read_isq

   density_arr, _ = read_aim("scan.AIM", density=True)
   hu_arr, _ = read_aim("scan.AIM", hu=True)
   isq_hu_arr, _ = read_isq("scan.ISQ", unit="hu")

RSQ raw detector projections
----------------------------

.. code-block:: python

   from py_aimio import image_info, read_image, read_rsq, rsq_info

   counts, meta = read_rsq("projections.RSQ;1", mmap=True)
   assert meta["axis_order"] == ("detector_row", "frame", "detector_column")
   header = rsq_info("projections.RSQ;1")

   # Automatic dispatch and the ReadImage/ImageInfo aliases also support RSQ.
   counts, meta = read_image("projections.RSQ", mmap=True)
   header = image_info("projections.RSQ")

.. code-block:: bash

   aimio-info projections.RSQ --format rsq

The supported RSQ interpretation reads ``CTDATA-HEADER_V1`` files as
little-endian unsigned 16-bit detector counts. Signedness is not independently
confirmed across all proprietary Scanco variants. Array shape is
``(header_words[13], header_words[12], header_words[11])`` in detector row,
frame, detector column order. ``mmap=True`` returns a read-only NumPy memmap;
the default loads counts into memory.

All stored frames are retained, including any reference frames. The reader does
not classify reference frames or require three frames; reconstruction must
validate its own view and reference requirements. RSQ arrays are raw projections.
Spatial volume, HU, and density conversion through ``read_image`` is unsupported
and raises ``ValueError``.

Metadata exposes the raw 128 unsigned ``header_words``, ``shape``,
``axis_order``, ``dtype``, and ``data_offset_bytes``. The ``geometry`` dictionary
contains partially inferred header hints with provenance and word positions:
requested output pitch, axial start, detector dimensions and sizes, source
distances, binning, object view count, and angular interval. Distances use
micrometers and angles use millidegrees. These hints do not provide reconstructed
volume ``origin``, ``spacing``, or ``direction``. The ``count_range`` from words
21 and 22 is not attenuation scaling. Patient-name fields are not decoded; raw
header words may still contain identifying data.

Validation requires the supported magic, positive dimensions, and exactly
``2 * product(shape)`` payload bytes after
``512 * (header_words[127] + 1)``. Zero-filled padding exactly to the next
512-byte block boundary is also accepted. Truncated payloads, nonzero padding,
and other trailing data are rejected. ``rsq_info`` reads the base header,
the final 512-byte header block, and any padding, using file size to validate
the payload. A recognized ``Beamhard.Corr.`` block
provides three little-endian float64 coefficients at bytes 476:500. The polynomial
``delta(p) = a1*p + a2*p**2 + a3*p**3`` must match printed ``Corr at 2 3 6:``
anchors with absolute tolerance ``1e-6`` and zero relative tolerance. Corrupt
recognized calibration raises ``ValueError``; missing or unrecognized calibration
is explicitly unavailable. Calibration is exposed in ``beam_hardening`` and is
not applied during raw reading.

RAD scout radiographs
---------------------

.. code-block:: python

   from py_aimio import read_rad, rad_info

   pixels, meta = read_rad("scout.RAD")
   header = rad_info("scout.RAD")
   print(pixels.shape)  # (row, column), a single 2D plane
   print(meta["spacing"])  # (x, y, display z) in mm

.. code-block:: bash

   aimio-info scout.RAD --format rad

The reader supports type-9 ``CTDATA-HEADER_V1`` radiographs and preserves
signed int16 native values. Header physical dimensions are in nanometres and
are converted to millimetres for in-plane spacing. The z spacing of 1 mm,
zero origin, and identity direction are display conventions, not CT
co-registration. Scanner reference and axial positions remain separate
metadata. HU/density conversion is not supported. Automatic image dispatch
also recognizes RAD, including filenames ending in VMS versions such as ``;1``.

SCV scout geometry
------------------

``read_scv`` accepts stream files and binary extracts with VMS variable-length
record wrappers without modifying the source. It decodes complete RLE rows
and VMS floating-point row coordinates. Scouts with uniform increasing row
coordinates retain the IPL-compatible header geometry. Repeated or nonuniform
coordinates, or invalid physical extents, trigger a warning and explicitly
labelled pixel-space geometry (unit spacing and zero origin). Original row
coordinates and header spacing remain available in metadata. Pixel-space
scouts are for viewing, not physical measurements or registration.
