#!/usr/bin/env python3
"""Generate the C preprocessor header dependency graph from a Clang compilation database."""
import argparse
import collections
import logging
import sys
from typing import Dict, Iterable, List, TextIO

from clang.cindex import (
    CompilationDatabase,
    CompilationDatabaseError,
    CompileCommand,
    FileInclusion,
    Index,
    TranslationUnit,
    TranslationUnitLoadError,
)

LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}
DEFAULT_LEVEL = "INFO"


def file_inclusion_repr(i: FileInclusion) -> str:
    return f"FileInclusion<source={i.source}, include={i.include}, location={i.location}, depth={i.depth}>"


# Make a FileInclusion printable
FileInclusion.__repr__ = file_inclusion_repr


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "build_dir",
        metavar="build-dir",
        type=str,
        help="The path to the build directory containing a compilation database.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="The file to save the output to. Defaults to stdout.",
    )
    parser.add_argument(
        "--output-format",
        "-O",
        type=str,
        default="tree",
        choices=["graphviz", "tree"],
        help="The output format for the parsed header dependency graph.",
    )
    # TODO: Trim common prefix from output?
    parser.add_argument(
        "--log-level",
        "-l",
        type=str,
        default=DEFAULT_LEVEL,
        choices=LOG_LEVELS.keys(),
        help=f"Set the logging output level. Defaults to {DEFAULT_LEVEL}.",
    )
    return parser.parse_args()


def load_compilation_database(build_dir: str) -> CompilationDatabase:
    """Load the compilation database from the given path."""
    try:
        return CompilationDatabase.fromDirectory(build_dir)
    except CompilationDatabaseError as e:
        logging.critical("Failed to load compilation database from '%s':", build_dir, exc_info=e)
        sys.exit(1)


def get_tu_includes(entry: CompileCommand, index: Index) -> Iterable[FileInclusion]:
    """Get the #includes from the given CompileCommand for a translation unit."""
    source_file = entry.filename
    compile_args = list(entry.arguments)
    # Strip off compiler (which is guaranteed to be there)
    compile_args = compile_args[1:]
    parse_options = TranslationUnit.PARSE_SKIP_FUNCTION_BODIES | TranslationUnit.PARSE_INCOMPLETE

    try:
        # Don't specify the filename, because if we do that _and_ leave the filename in the compiler
        # arguments, it can't parse the translation unit
        tu = TranslationUnit.from_source(
            filename=None, args=compile_args, options=parse_options, index=index
        )
        # TODO: Unfortunately, this only includes (ba dum tshh) headers that were _actually_
        # included, and thus, because of header guards, can't show circular dependencies, even
        # though that would be _immensely_ useful.
        #
        # I think to solve this, I _have_ to invoke CXX with -E and munge the stdout output.
        # This way, the context of the "ifndef, define" and "pragma once" header guards get lost for
        # each file, so you get the full graph.
        includes = tu.get_includes()
        return includes
    except TranslationUnitLoadError as e:
        logging.error(
            "Failed to load translation unit from compilation database for: '%s'",
            source_file,
            exc_info=e,
        )
    return []


def get_project_includes(database: CompilationDatabase) -> Iterable[FileInclusion]:
    """Get the #includes from the given compilation database."""
    exclude_local_declarations = True
    index = Index.create(exclude_local_declarations)
    compile_commands = database.getAllCompileCommands()
    for entry in compile_commands:
        logging.debug("Getting headers for %s", entry.filename)
        entry_headers = get_tu_includes(entry, index)
        yield from entry_headers


def build_header_dependency_graph(includes: Iterable[FileInclusion]) -> Dict:
    """Build a dependency graph from a set of FileInclusion objects."""
    graph = collections.defaultdict(list)
    file_include: FileInclusion
    for file_include in includes:
        # logging.debug("Found header inclusion: %s -> %s", file_include.source, file_include.include)
        source = file_include.source#.name
        included_file = file_include.include#.name
        graph[source].append(included_file)

    return graph


def topological_sort(graph: Dict[str, List[str]]) -> List[str]:
    """Topologically sort the keys of a graph."""
    sorted_keys = []
    seen = set()

    def recursive_helper(node: str):
        for neighbor in graph.get(node, []):
            if neighbor not in seen:
                seen.add(neighbor)
                recursive_helper(neighbor)
        if node not in sorted_keys:
            sorted_keys.append(node)

    for key in graph.keys():
        recursive_helper(key)
    return sorted_keys


def output_dep_graph_tree(graph: Dict, file: TextIO):
    """Output the include graph as a tree.

    Example:
        example1.cpp
            foo.h
            bar.h
            private.h
                circular.h

    Each level of indentation will be a single tab character.
    """

    def recursive_dfs_helper(graph: Dict, source: str, file: TextIO, depth: int, path=[]):
        indent = "\t" * depth
        print(f"{indent}{source}", file=file)
        if source not in path:
            path.append(source)
            if source not in graph:
                return path
            for neighbor in graph[source]:
                path = recursive_dfs_helper(graph, neighbor, file, depth + 1, path)
        return path

    # Get a top-level candidate (is not depended on by anything else) to print first at depth=0
    sorted_keys = topological_sort(graph)
    root = sorted_keys[-1]

    recursive_dfs_helper(graph, root, file, depth=0)


def output_dep_graph_graphviz(graph: Dict, file: TextIO):
    """Output the include graph in Graphviz format."""
    print("digraph header_graph {", file=file)
    for source, targets in graph.items():
        for target in targets:
            print(f'\t"{source}" -> "{target}";', file=file)
    print("}", file=file)


def output_dep_graph(graph: Dict, file: TextIO, format: str):
    if format == "tree":
        output_dep_graph_tree(graph, file)
    elif format == "graphviz":
        output_dep_graph_graphviz(graph, file)


def main(args):
    database = load_compilation_database(args.build_dir)
    logging.debug(
        "Successfully loaded compilation database from build directory '%s'", args.build_dir
    )
    includes = get_project_includes(database)
    include_graph = build_header_dependency_graph(includes)
    output_dep_graph(include_graph, args.output, args.output_format)


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=LOG_LEVELS.get(args.log_level),
        stream=sys.stderr,
    )
    logging = logging.getLogger(name=__file__)
    main(args)
