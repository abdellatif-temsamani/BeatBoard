#!/bin/bash

# Safety check
if [ ! -f pyproject.toml ]; then
    echo "Error: Not in BeatBoard project root"
    exit 1
fi

rm -fr dist
python -m build && pipx install dist/*.whl
