#!/usr/bin/env python3
"""Filter a TGF graph generated by includegraph.py.

There are two kinds of rules you can use to query the dependency graph.
1. (--filter) You can filter out specific subtrees that match a given glob
2. (--keep-only) You can filter out everything _except_ subtrees that match a given glob

These two options can be given multiple times. If both --keep-only and --filter globs are given, the
--filter globs are applied after the --keep-only globs.
"""
import argparse
import collections
import functools
import itertools
import logging
import sys
from pathlib import Path, PurePath
from typing import Callable, Dict, Iterable, List, Set, Tuple

# This is kind of hacky, but there's two other options:
# 1. duplicate the shared stuff and hope they stay in sync
# 2. add an includegraph library, and require it gets installed in order to use the scripts
# I don't like the first option because it's a maintenance nightmare, but I also don't like the
# second option because it increases the friction to use these tools.
repo_root = Path(__file__).resolve().parent
repo_root = str(repo_root)
sys.path.insert(0, repo_root)
try:
    from includegraph import output_dep_graph_tgf
    from tgf2graphviz import IncludeGraph, IncludeGraphNode, parse_tgf_graph
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
        help="The path to the input graph. Defaults to stdin.",
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
    parser.add_argument(
        "--shorten-file-paths",
        "-s",
        action="store_true",
        default=False,
        help="Shorten absolute node file paths",
    )
    parser.add_argument(
        "--filter-transitive-system-headers",
        action="store_true",
        default=False,
        help="Remove system headers included by another system header.",
    )
    parser.add_argument(
        "--filter-system-headers",
        action="store_true",
        default=False,
        help="Remove all system headers from the graph.",
    )
    parser.add_argument(
        "--filter",
        "-f",
        type=str,
        action="append",
        help="Remove subtrees where the root nodes match the given filepath glob(s). Applied after any --keep-only globs, if any are present.",
    )
    parser.add_argument(
        "--keep-only",
        "-k",
        type=str,
        action="append",
        help="Keep only subtrees where the root node matches the given filepath glob(s)",
    )
    return parser.parse_args()


def map_basenames_to_absolute(paths: Iterable[str]) -> Dict[str, Set[str]]:
    """Map the file basenames to their absolute paths.

    Example input:
        /a/b/c.h
        /a/b/d.h
        /a/c/c.h

    Example output:
        c.h -> {/a/b/c.h, /a/c/c.h}
        d.h -> {/a/b/d.h, }

    A helper for shorten_absolute_paths.
    """
    mapping = collections.defaultdict(set)
    for path in paths:
        path = PurePath(path)
        mapping[path.name].add(str(path))

    return mapping


def all_equal(s: Iterable) -> bool:
    """Determine if every element of the given iterable are equal."""
    g = itertools.groupby(s)
    return next(g, True) and not next(g, False)


def shortest_unique_suffixes(paths: Set[str]) -> Dict[str, str]:
    """Find the shortest unique suffix for each of the given strings.

    Example input:
        {/a/b/c.h, /a/c/c.h}

    Example output:
        /a/b/c.h -> b/c.h
        /a/c/c.h -> c/c.h
    """
    paths = list(paths)  # need deterministic ordering, so no set for you.
    path_parts = (PurePath(p) for p in paths)
    path_parts = (reversed(p.parts) for p in path_parts)
    path_parts = zip(*path_parts)

    # Start at the end:
    # 0. (c.h, c.h)  # Equal, continue
    # 1. (b/, c/)    # Not equal, break
    # This results in:
    # [(c.h, c.h), (b/, c/)]
    suffixes = []
    for level in path_parts:
        # create the suffix for each path
        suffixes.append(level)
        if len(level) == 1 or not all_equal(level):
            break

    # Then we take
    # [(c.h, c.h), (b/, c/)]
    # and prepend the levels to generate
    # (b/c.h, c/c.h)
    def prepend_levels(level1: Tuple[str], level2: Tuple[str]) -> Tuple[str]:
        return tuple(PurePath(l2) / l1 for l1, l2 in zip(level1, level2))

    suffixes = functools.reduce(prepend_levels, suffixes)
    suffixes = (str(s) for s in suffixes)
    suffixes = dict(zip(paths, suffixes))
    return suffixes


def shorten_absolute_paths(paths: Iterable[str]) -> Dict[str, str]:
    """Shorten the given absolute paths into the shortest unique suffix.

    Example input:
        /a/b/c.h
        /a/b/d.h
        /a/c/c.h

    Example output:
        /a/b/c.h -> b/c.h
        /a/b/d.h -> d.h
        /a/c/c.h -> c/c.h

    That is, the returned dictionary maps the absolute paths to their shortened form.
    """
    suffixes = {}
    # Determine if there are multiple occurrences of the same header
    multiple_occurrences = map_basenames_to_absolute(paths)
    for basename, occurrences in multiple_occurrences.items():
        # Nominal case. There's no need to find the shortest suffix.
        if len(occurrences) == 1:
            absolute = occurrences.pop()
            suffix = basename
            suffixes[absolute] = suffix
        else:
            suffixes.update(shortest_unique_suffixes(occurrences))

    return suffixes


def matches_globs(s: str, patterns: List[str]) -> bool:
    path = PurePath(s)
    for pattern in patterns:
        if path.match(pattern):
            return True
    return False


def bfs(
    graph: IncludeGraph,
    source: IncludeGraphNode,
    visitor: Callable[IncludeGraphNode, Set[IncludeGraphNode]],
):
    """Perform a breadth first search of the given graph starting at 'node'.

    Calls 'visitor' on each node visited. The visitor returns the node's children. This is useful as
    a mechanism to influence the graph traversal (e.g., early exit)
    """
    visited = set()
    queue = collections.deque([source])
    while queue:
        current = queue.popleft()
        visited.add(current)
        children = visitor(current)
        for child in children:
            if child not in visited:
                queue.append(child)
                visited.add(child)


def dfs(
    graph: IncludeGraph,
    source: IncludeGraphNode,
    visitor: Callable[IncludeGraphNode, Set[IncludeGraphNode]],
):
    """Perform a depth first search of the given graph starting at 'node'.

    Calls 'visitor' on each node visited. The visitor returns the node's children. This is useful as
    a mechanism to influence the graph traversal (e.g., early exit)
    """
    visited = set()
    # With the iterative algorithm, the only difference between DFS and BFS is it uses a stack
    # instead of a queue.
    stack = [source]
    while stack:
        current = stack.pop()
        visited.add(current)
        children = visitor(current)
        for child in children:
            if child not in visited:
                stack.append(child)
                visited.add(child)


def filter_graph(
    graph: IncludeGraph,
    filter_globs: List[str],
    filter_system_headers=False,
    filter_transitive_system_headers=False,
) -> IncludeGraph:
    """Filter the given graph by a list of filter globs.

    * Add metadata to each node when parsing the graph
        * number of in-edges
    * Build a set of unvisited nodes
    * Search for nodes matching the filter pattern
        * Pick an unvisited node
            * optimization - pick a node with zero in-edges
        * BFS, look for nodes that match the filter pattern
            * If a matching node was found
                * BFS
                    * Remove any node with less than 2 in-edges
                    * Early return (one stack frame) if all adjacent edges have at least 2 in-edges
    """
    unvisited_nodes = set(graph.keys())
    nodes_to_delete = set()

    def remove_if_not_included_by_something_else(node: IncludeGraphNode) -> bool:
        # If multiple nodes include this one, we can't remove it, or any of its children
        # Additionally, since we're iterating over the graph as we're removing nodes, we should skip
        # anything that's already been removed.
        if node.num_in_edges > 1 or node not in graph:
            logging.debug("\t\t\tcan't remove %s", node)
            return set()

        logging.debug("\t\t\tRemoving %s", node)
        children = graph[node]
        nodes_to_delete.add(node)
        return children

    def remove_subtree_of_matching_node(node: IncludeGraphNode):
        logging.info("\t\tRemoving subtree for node %s", node)
        # Do another BFS search starting from this node, removing each visited node, if it wasn't
        # included by another node.
        bfs(graph, node, remove_if_not_included_by_something_else)
        while nodes_to_delete:
            node = nodes_to_delete.pop()
            for child in graph[node]:
                child.num_in_edges -= 1
            del graph[node]

    def remove_nodes_matching_glob(node: IncludeGraphNode) -> Set[IncludeGraphNode]:
        # Mark this node as visited
        unvisited_nodes.discard(node)
        logging.debug("\tVisiting %s", node)
        matches_glob = matches_globs(node.filename, filter_globs)
        system_header = filter_system_headers and node.is_system_header
        transitive_system_header = (
            filter_transitive_system_headers
            and node.is_system_header
            # TODO: Make this is_transitive_system_header
            and not node.is_first_level_system_header
        )

        if matches_glob or system_header or transitive_system_header:
            remove_subtree_of_matching_node(node)
        return graph.get(node, set())

    while unvisited_nodes:
        # This is how you have to iterate over a set that changes size. Unfortunately though, it
        # introduces randomness.
        root = unvisited_nodes.pop()
        unvisited_nodes.add(root)

        # From this root, look for nodes that match any of our filters
        logging.debug("Starting search from %s", root)
        bfs(graph, root, remove_nodes_matching_glob)

    for source, targets in graph.items():
        graph[source] = set(t for t in targets if t in graph)

    return graph


def recalculate_in_edges(graph: IncludeGraph) -> IncludeGraph:
    """Recalculate the number of in-edges for each node."""
    nodes = {}
    for node in graph.keys():
        node.num_in_edges = 0
        nodes[node.filename] = node

    for source, targets in graph.items():
        for target in targets:
            nodes[target.filename].num_in_edges += 1
    return graph


def filter_all_except(graph: IncludeGraph, exclusion_globs: List[str]) -> IncludeGraph:
    """Filter everything except subtrees where the root matches some exclusion pattern."""
    nodes_to_keep = set()
    unvisited_nodes = set(graph.keys())

    def mark_as_keep(node: IncludeGraphNode) -> Set[IncludeGraphNode]:
        logging.debug("\tKeeping %s", node)
        unvisited_nodes.discard(node)
        nodes_to_keep.add(node)
        return graph[node]

    while unvisited_nodes:
        node = unvisited_nodes.pop()
        if matches_globs(node.filename, exclusion_globs):
            bfs(graph, node, mark_as_keep)

    graph = {n: t for n, t in graph.items() if n in nodes_to_keep}
    for source, targets in graph.items():
        graph[source] = set(t for t in targets if t in graph)

    # The number of in-edges is calculated during graph parsing, but it's necessary to be correct
    # for filter_graph() to work, so if we modify the graph, we need to update the edge count.
    graph = recalculate_in_edges(graph)
    return graph


def main(args):
    graph: IncludeGraph = parse_tgf_graph(args.input)

    if args.keep_only:
        graph = filter_all_except(graph, args.keep_only)

    if args.filter:
        graph = filter_graph(
            graph, args.filter, args.filter_system_headers, args.filter_transitive_system_headers
        )

    if args.shorten_file_paths:
        logging.debug("Shortening absolute file paths...")
        paths = [node.filename for node in graph]
        shortened_filenames = shorten_absolute_paths(paths)
        for node in graph:
            shortened_filename = shortened_filenames.get(node.filename, node.filename)
            node.filename = shortened_filename

    output_dep_graph_tgf(graph, args.output)


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(
        format="%(asctime)s - %(module)s - %(levelname)s - %(message)s",
        level=LOG_LEVELS.get(args.log_level),
        stream=sys.stderr,
    )
    main(args)
