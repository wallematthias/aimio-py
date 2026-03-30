from setuptools import setup, Extension
import os
import sys

# project root
here = os.path.dirname(__file__)

def gather_sources():
    here = os.path.dirname(__file__)
    src = [os.path.join('bindings','aimio_bindings.cpp')]
    aimio_dir = os.path.join(here, 'AimIO')
    if os.path.isdir(aimio_dir):
        for root, _, files in os.walk(os.path.join(aimio_dir, 'source')):
            for f in files:
                if not f.endswith(('.cxx', '.cpp', '.cc')):
                    continue
                # skip example / tool files that define main or duplicate symbols
                if f in ('aix.cxx', 'ctheader.cxx'):
                    continue
                src.append(os.path.relpath(os.path.join(root, f), here))
    return src

from setuptools import setup
try:
    import pybind11
    import numpy
    include_dirs = [pybind11.get_include(), numpy.get_include(), os.path.join('AimIO','include')]
    # add n88util headers if provided as a submodule
    n88_include = os.path.join(here, 'n88util', 'include')
    if os.path.isdir(n88_include):
        include_dirs.append(n88_include)
except Exception:
    include_dirs = [os.path.join('AimIO','include')]

ext = Extension(
    'py_aimio._aimio',
    sources=gather_sources(),
    include_dirs=include_dirs,
    language='c++',
    extra_compile_args=['-std=c++17'] if sys.platform != 'win32' else ['/std:c++17']
)

setup(
    ext_modules=[ext],
)
