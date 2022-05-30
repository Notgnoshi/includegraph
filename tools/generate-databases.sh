#!/bin/bash
set -o errexit
set -o pipefail
set -o nounset
set -o noclobber

REPO_DIRECTORY="$(git rev-parse --show-toplevel)"
for example in "$REPO_DIRECTORY"/examples/example*; do
    build_dir="$example/build"
    compdb="$build_dir/compile_commands.json"
    cmake -S "$example" -B "$build_dir" >&2

    # Don't need to do the build for the compilation database to be useful, but do it anyways,
    # because it copies the database into the example directory, so that it can be checked into Git.
    cmake --build "$build_dir" >&2

    if [[ ! -f "$compdb" ]]; then
        echo "Failed to generate '$compdb'" >&2
    else
        echo "Generated $compdb"
    fi
done
