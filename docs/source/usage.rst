Usage
=====

Install
-------

.. code-block:: bash

   pip install py-aimio

Minimal read/write example
--------------------------

.. code-block:: python

   from py_aimio import read_aim, read_isq, write_aim

   arr, meta = read_aim("scan.AIM")
   write_aim("copy.AIM", arr, meta)

   isq_arr, isq_meta = read_isq("scan.ISQ")

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

   from py_aimio import read_aim

   density_arr, _ = read_aim("scan.AIM", density=True)
   hu_arr, _ = read_aim("scan.AIM", hu=True)
