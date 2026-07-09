# ISQ Fixtures

`test_isq_calibrated_binary_25.ISQ` is a tiny 25 x 25 x 25 binary ISQ with an
extended calibration header. Native values are 0/1. HU conversion gives
-1000/-999, and density/BMD conversion gives 3/5.

`test_isq_native_only_binary_25.ISQ` uses the same binary image data but has no
extended calibration header. It can only be read in native units.

Both files are intentionally small and are readable by AimIO and ITKIOScanco.
