"""
 C Library import.
"""
import os
import pathlib
from ctypes import cdll

_LIB_DEFAULT_LOCATION = os.path.join(
    pathlib.Path(__file__).parent.resolve().parent.resolve(), ".extensions", "nexus_sdk.so"
)
CLIB = cdll.LoadLibrary(_LIB_DEFAULT_LOCATION)
