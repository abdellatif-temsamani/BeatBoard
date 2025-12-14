#!/bin/bash

rm -fr dist
python -m build && pipx install dist/*.whl
