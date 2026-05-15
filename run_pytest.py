#!/usr/bin/env python3
"""Run pytest and display results."""
import subprocess
import sys

result = subprocess.run(
    ["python", "-m", "pytest", "tests/test_analyze.py", "-v", "--tb=short"],
    cwd="/github/workspace"
)
sys.exit(result.returncode)
