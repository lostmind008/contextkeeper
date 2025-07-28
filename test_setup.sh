#!/bin/bash

# Create a virtual environment
python3 -m venv test_venv

# Activate the virtual environment
source test_venv/bin/activate

# Install the dependencies
pip install -v -r requirements.txt

# Run the tests
pytest -v tests/
