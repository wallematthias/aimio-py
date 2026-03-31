Usage
=====

Install
-------

.. code-block:: bash

   pip install py-aimio

Minimal read/write example
--------------------------

.. code-block:: python

   from py_aimio import read_aim, write_aim

   arr, meta = read_aim("scan.AIM")
   write_aim("copy.AIM", arr, meta)

Metadata-only example
---------------------

.. code-block:: python

   from py_aimio import aim_info

   info = aim_info("scan.AIM")
   print("Dimensions:", info["dimensions"])

Density/HU conversion example
-----------------------------

.. code-block:: python

   from py_aimio import read_aim

   density_arr, _ = read_aim("scan.AIM", density=True)
   hu_arr, _ = read_aim("scan.AIM", hu=True)
