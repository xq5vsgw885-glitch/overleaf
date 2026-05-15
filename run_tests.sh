#!/bin/bash
cd /tmp/test_repo 2>/dev/null || cd . && python -m pytest tests/test_analyze.py -v
