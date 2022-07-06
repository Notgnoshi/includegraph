#!/usr/bin/env python3
"""Convert TGF graphs to Graphviz format."""
import argparse
import ast
import logging
import shlex
import sys
from pathlib import Path
from typing import Dict, Generator, TextIO, Tuple

# This is kind of hacky, but there's two other options:
# 1. duplicate the shared stuff and hope they stay in sync
# 2. add an includegraph library, and require it gets installed in order to use the scripts
# I don't like the first option because it's a maintenance nightmare, but I also don't like the
# second option because it increases the friction to use these tools.
repo_root = Path(__file__).resolve().parent
repo_root = str(repo_root)
sys.path.insert(0, repo_root)
try:
    from includegraph import IncludeGraph, IncludeGraphNode
except ImportError:
    logging.critical("Failed to import types from includegraph.py.")
    raise

LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}
DEFAULT_LEVEL = "INFO"


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--input",
        "-i",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="The file to read input from. Defaults to stdin.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="The file to save the output to. Defaults to stdout.",
    )
    parser.add_argument(
        "--log-level",
        "-l",
        type=str,
        default=DEFAULT_LEVEL,
        choices=LOG_LEVELS.keys(),
        help=f"Set the logging output level. Defaults to {DEFAULT_LEVEL}.",
    )
    return parser.parse_args()


def parse_tgf_node_list(
    lines: Generator[str, None, None]
) -> Generator[IncludeGraphNode, None, None]:
    """Parse the node list from a TGF graph."""
    for line in lines:
        line = line.strip()

        # We reached the separator between the node list and the edges
        if line.startswith("#"):
            break

        filename, *attributes = shlex.split(line)
        filename = filename.strip("'\"")

        node = IncludeGraphNode(filename=filename)
        if attributes:
            attributes = ", ".join(attributes)
            attributes = attributes.strip("'\"")
            attributes = attributes.split(",")
            try:
                for attr in attributes:
                    attr = attr.strip()
                    lhs, rhs = attr.split("=")
                    if getattr(node, lhs, None) is not None:
                        value = ast.literal_eval(rhs)
                        setattr(node, lhs, value)
            except BaseException:
                logging.error("Failed to parse attributes for %s", filename, exc_info=True)
                continue
        yield node


def parse_tgf_edge_list(
    lines: Generator[str, None, None], nodes: Dict[str, IncludeGraphNode]
) -> Generator[Tuple[IncludeGraphNode, IncludeGraphNode], None, None]:
    """Parse the edge list from a TGF graph."""
    for line in lines:
        line = line.strip()
        source, target = None, None
        try:
            source, target, *label = shlex.split(line)
            source = source.strip("'\"")
            target = target.strip("'\"")

            # We don't do anything with the label, if it's there, but parse it anyways.
            label = " ".join(label)
            label = label.strip("'\"")
        except BaseException:
            logging.error("Failed to parse edge from '%s'", line)
            continue
        # We can't just do graph[source].add(target) because the types in the graph are actual
        # objects, not the string file names. So we need to look up the nodes in the graph keys.
        source = nodes.get(source, None)
        target = nodes.get(target, None)
        if source is None or target is None:
            logging.error("Edge line '%s' refers to a node not in the node list", line)
            continue
        yield source, target


def parse_tgf_graph(input: TextIO) -> IncludeGraph:
    """Parse an include graph in Trivial Graph Format.

    Supports node metadata, but not edge metadata.

    Example:
        "/usr/include/stdc-predef.h"    "is_source_file=False, is_system_header=True,  is_first_level_system_header=True"
        "include/example2/foo.h"        "is_source_file=False, is_system_header=False, is_first_level_system_header=False"
        "include/example2/bar.h"        "is_source_file=False, is_system_header=False, is_first_level_system_header=False"
        "src/private.h"                 "is_source_file=False, is_system_header=False, is_first_level_system_header=False"
        "src/circular.h"                "is_source_file=False, is_system_header=False, is_first_level_system_header=False"
        #
        "src/example2.cpp"              "src/private.h"
        "src/example2.cpp"              "/usr/include/stdc-predef.h"
        "src/example2.cpp"              "include/example2/foo.h"
        "src/example2.cpp"              "include/example2/bar.h"
        "src/private.h"                 "src/circular.h"
    """
    # Needs to be an iterator so the second loop remembers where the first left off.
    lines = iter(input.readlines())

    nodes_iter = parse_tgf_node_list(lines)
    graph: IncludeGraph = {}
    nodes: Dict[str, IncludeGraphNode] = {}
    for node in nodes_iter:
        nodes[node.filename] = node
        graph[node] = set()
    edges = parse_tgf_edge_list(lines, nodes)
    for source, target in edges:
        graph[source].add(target)

    return graph


def graphviz_node_attributes(node: IncludeGraphNode) -> str:
    rval = ""

    if node.is_source_file:
        rval = " [shape=box, fillcolor=lightgray, style=filled]"
    elif node.is_system_header:
        rval = " [style=dashed]"

    return rval


def output_graphviz_graph(graph: IncludeGraph, output: TextIO):
    print("digraph include_dependency_graph {", file=output)
    for src in graph.keys():
        attributes = graphviz_node_attributes(src)
        print(f'  "{src.filename}"{attributes};', file=output)

    print("", file=output)
    for src in graph.keys():
        for tgt in graph[src]:
            print(f'  "{src.filename}" -> "{tgt.filename}";', file=output)
    print("}", file=output)


def main(args):
    graph = parse_tgf_graph(args.input)
    output_graphviz_graph(graph, args.output)


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(
        format="%(asctime)s - %(module)s - %(levelname)s - %(message)s",
        level=LOG_LEVELS.get(args.log_level),
        stream=sys.stderr,
    )
    main(args)
