#!/usr/bin/env python
"""Entry point for the People-Work Report Generator CLI. See `python render.py --help`."""
import sys

from app.cli import main

if __name__ == "__main__":
    sys.exit(main())
