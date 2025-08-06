#!/bin/bash

# This script runs the initial training process under the cProfile profiler
# to identify performance bottlenecks.

# --- Instructions ---
# 1. Make sure you have an active virtual environment with all dependencies installed.
# 2. Run this script from the project root directory:
#    bash scripts/profile_training.sh
# 3. This will generate a file named `train.prof` in the root directory.
# 4. To visualize the profiling results, install snakeviz:
#    pip install snakeviz
# 5. Run snakeviz on the output file:
#    snakeviz train.prof
# --------------------

echo "--- Starting profiling of train_initial_models.py ---"

python -m cProfile -o train.prof scripts/train_initial_models.py

echo "--- Profiling finished. ---"
echo "Output saved to train.prof"
echo "To visualize, run: snakeviz train.prof"
