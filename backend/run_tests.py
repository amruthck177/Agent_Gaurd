"""
backend/run_tests.py

Convenience runner for pytest that ensures sys.path is sanitized
from any rogue py.py in the python root directory.
"""

import sys

# Remove base Python directory if it shadows pytest
sys.path = [p for p in sys.path if p.rstrip("\\/") != r"C:\Users\amrut\AppData\Local\Programs\Python\Python313"]

import pytest

if __name__ == "__main__":
    args = sys.argv[1:] if len(sys.argv) > 1 else ["tests"]
    sys.exit(pytest.main(args))
