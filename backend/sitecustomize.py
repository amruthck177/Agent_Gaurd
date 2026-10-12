"""
sitecustomize.py

Ensures C:\\Users\\amrut\\AppData\\Local\\Programs\\Python\\Python313 is stripped from sys.path
so that any rogue py.py in the python home folder does not shadow pytest's dependencies.
"""

import os
import sys

sys.path = [p for p in sys.path if p.rstrip("\\/") != r"C:\Users\amrut\AppData\Local\Programs\Python\Python313"]

# Ensure workspace root is in sys.path so agent package is importable
_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT_DIR not in sys.path and os.path.isdir(_ROOT_DIR):
    sys.path.insert(0, _ROOT_DIR)
