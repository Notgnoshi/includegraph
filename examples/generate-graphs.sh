#!/bin/bash
set -o errexit
set -o pipefail
set -o nounset
set -o noclobber

REPO_DIRECTORY="$(git rev-parse --show-toplevel)"
for example in "$REPO_DIRECTORY"/examples/example*; do
    build_dir="$example/build"
    compdb="$build_dir/compile_commands.json"
    graph="$example/graph.svg"

    "$REPO_DIRECTORY/includegraph.py" \
        --output-format graphviz \
        --log-level DEBUG \
        "$compdb" |
        dot -Tsvg -o "$graph"
done
