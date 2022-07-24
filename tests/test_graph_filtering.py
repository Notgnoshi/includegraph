import copy
import io

from filtergraph import (
    bfs,
    dfs,
    filter_all_except,
    filter_graph,
    map_basenames_to_absolute,
    output_dep_graph_tgf,
    parse_tgf_graph,
    shorten_absolute_paths,
    shortest_unique_suffixes,
)

example1_input = [
    "/a/b/c.h",
    "/a/b/d.h",
    "/a/c/c.h",
]
example1_absolute_mapping = {
    "c.h": {"/a/b/c.h", "/a/c/c.h"},
    "d.h": {
        "/a/b/d.h",
    },
}
example1_shortened_mapping = {
    "/a/b/c.h": "b/c.h",
    "/a/b/d.h": "d.h",
    "/a/c/c.h": "c/c.h",
}


def lines2textio(lines):
    buffer = "\n".join(lines).encode("utf-8")
    return io.TextIOWrapper(io.BytesIO(buffer))


def remove_indices(l, indices):
    return [v for i, v in enumerate(l) if i not in indices]


def edges(graph):
    for source, targets in graph.items():
        for target in targets:
            yield (source, target)


def edge_list(graph):
    e = list(edges(graph))
    return sorted(e)


def assert_graph_equal(lhs, rhs):
    # Nodes
    assert sorted(lhs.keys()) == sorted(rhs.keys())
    # Edges
    assert edge_list(lhs) == edge_list(rhs)


example2_input = [
    '"src/example2.cpp"	"is_source_file=True, is_system_header=False, is_first_level_system_header=False"',  # 0
    '"/usr/include/stdc-predef.h"	"is_source_file=False, is_system_header=True, is_first_level_system_header=True"',  # 1
    '"include/example2/foo.h"	"is_source_file=False, is_system_header=False, is_first_level_system_header=False"',  # 2
    '"include/example2/bar.h"	"is_source_file=False, is_system_header=False, is_first_level_system_header=False"',  # 3
    '"src/private.h"	"is_source_file=False, is_system_header=False, is_first_level_system_header=False"',  # 4
    '"src/circular.h"	"is_source_file=False, is_system_header=False, is_first_level_system_header=False"',  # 5
    "#",  # 6
    '"src/example2.cpp" "include/example2/bar.h"',  # 7
    '"src/example2.cpp" "src/private.h"',  # 8
    '"src/example2.cpp" "include/example2/foo.h"',  # 9
    '"src/example2.cpp" "/usr/include/stdc-predef.h"',  # 10
    '"src/private.h" "src/circular.h"',  # 11
]
example2_graph = parse_tgf_graph(lines2textio(example2_input))

example4_input = [
    '"a.cpp"    "is_source_file=True, is_system_header=False, is_first_level_system_header=False"',  # 0
    '"b.cpp"    "is_source_file=True, is_system_header=False, is_first_level_system_header=False"',  # 1
    '"c.cpp"    "is_source_file=True, is_system_header=False, is_first_level_system_header=False"',  # 2
    '"a.h"      "is_source_file=False, is_system_header=False, is_first_level_system_header=False"',  # 3
    '"foo.h"    "is_source_file=False, is_system_header=False, is_first_level_system_header=False"',  # 4
    '"b.h"      "is_source_file=False, is_system_header=False, is_first_level_system_header=False"',  # 5
    '"c.h"      "is_source_file=False, is_system_header=False, is_first_level_system_header=False"',  # 6
    '"vector"   "is_source_file=False, is_system_header=True, is_first_level_system_header=True"',  # 7
    '"string"   "is_source_file=False, is_system_header=True, is_first_level_system_header=True"',  # 8
    "#",  # 9
    '"a.cpp"    "a.h"',  # 10
    '"a.cpp"    "foo.h"',  # 11
    '"b.cpp"    "b.h"',  # 12
    '"b.cpp"    "string"',  # 13
    '"c.cpp"    "c.h"',  # 14
    '"a.h"      "vector"',  # 15
    '"foo.h"    "string"',  # 16
    '"b.h"      "foo.h"',  # 17
    '"b.h"      "string"',  # 18
]
example4_graph = parse_tgf_graph(lines2textio(example4_input))

# The same as example4, except with a circular foo.h <-> b.h dependency
example5_input = [
    '"a.cpp"    "is_source_file=True, is_system_header=False, is_first_level_system_header=False"',  # 0
    '"b.cpp"    "is_source_file=True, is_system_header=False, is_first_level_system_header=False"',  # 1
    '"c.cpp"    "is_source_file=True, is_system_header=False, is_first_level_system_header=False"',  # 2
    '"a.h"      "is_source_file=False, is_system_header=False, is_first_level_system_header=False"',  # 3
    '"foo.h"    "is_source_file=False, is_system_header=False, is_first_level_system_header=False"',  # 4
    '"b.h"      "is_source_file=False, is_system_header=False, is_first_level_system_header=False"',  # 5
    '"c.h"      "is_source_file=False, is_system_header=False, is_first_level_system_header=False"',  # 6
    '"vector"   "is_source_file=False, is_system_header=True, is_first_level_system_header=True"',  # 7
    '"string"   "is_source_file=False, is_system_header=True, is_first_level_system_header=True"',  # 8
    "#",  # 9
    '"a.cpp"    "a.h"',  # 10
    '"a.cpp"    "foo.h"',  # 11
    '"b.cpp"    "b.h"',  # 12
    '"b.cpp"    "string"',  # 13
    '"c.cpp"    "c.h"',  # 14
    '"a.h"      "vector"',  # 15
    '"foo.h"    "string"',  # 16
    '"b.h"      "foo.h"',  # 17
    '"b.h"      "string"',  # 18
    '"foo.h"    "b.h"',  # 19
]
example5_graph = parse_tgf_graph(lines2textio(example5_input))


def test_bfs():
    path = []
    graph = example4_graph

    def visitor(node):
        path.append(node)
        # sort the children for deterministic tests
        return sorted(list(graph[node]))

    source = [k for k in graph.keys() if k.filename == "a.cpp"][0]
    bfs(graph, source, visitor)
    path = [n.filename for n in path]
    assert path == ["a.cpp", "a.h", "foo.h", "vector", "string"]


def test_bfs_circular():
    path = []
    graph = example5_graph

    def visitor(node):
        path.append(node)
        # sort the children for deterministic tests
        return sorted(list(graph[node]))

    source = [k for k in graph.keys() if k.filename == "a.cpp"][0]
    bfs(graph, source, visitor)
    path = [n.filename for n in path]
    assert path == ["a.cpp", "a.h", "foo.h", "vector", "b.h", "string"]


def test_dfs():
    path = []
    graph = example4_graph

    def visitor(node):
        path.append(node)
        # sort the children for deterministic tests
        return sorted(list(graph[node]))

    source = [k for k in graph.keys() if k.filename == "a.cpp"][0]
    dfs(graph, source, visitor)
    path = [n.filename for n in path]
    assert path == ["a.cpp", "foo.h", "string", "a.h", "vector"]


def test_dfs_circular():
    path = []
    graph = example5_graph

    def visitor(node):
        path.append(node)
        # sort the children for deterministic tests
        return sorted(list(graph[node]))

    source = [k for k in graph.keys() if k.filename == "a.cpp"][0]
    dfs(graph, source, visitor)
    path = [n.filename for n in path]
    assert path == ["a.cpp", "foo.h", "string", "b.h", "a.h", "vector"]


def test_example2_no_filtering():
    globs = []
    graph = copy.deepcopy(example2_graph)
    expected_graph = parse_tgf_graph(lines2textio(example2_input))
    filtered_graph = filter_graph(graph, globs)
    assert_graph_equal(filtered_graph, expected_graph)


def test_example2_filter_system():
    globs = []
    graph = copy.deepcopy(example2_graph)
    expected_graph_inputs = remove_indices(example2_input, [1, 10])
    expected_graph = parse_tgf_graph(lines2textio(expected_graph_inputs))
    filtered_graph = filter_graph(graph, globs, filter_system_headers=True)
    assert_graph_equal(filtered_graph, expected_graph)


def test_example2_filter_circular():
    globs = ["src/circular.h"]
    graph = copy.deepcopy(example2_graph)
    expected_graph_inputs = remove_indices(example2_input, [5, 11])
    expected_graph = parse_tgf_graph(lines2textio(expected_graph_inputs))
    filtered_graph = filter_graph(graph, globs)
    assert_graph_equal(filtered_graph, expected_graph)


def test_example2_filter_private_headers():
    globs = ["src/*.h"]
    graph = copy.deepcopy(example2_graph)
    expected_graph_inputs = remove_indices(example2_input, [4, 5, 8, 11])
    expected_graph = parse_tgf_graph(lines2textio(expected_graph_inputs))
    filtered_graph = filter_graph(graph, globs)
    assert_graph_equal(filtered_graph, expected_graph)


def test_example2_filter_public_headers():
    globs = ["include/*/*.h"]
    graph = copy.deepcopy(example2_graph)
    expected_graph_inputs = remove_indices(example2_input, [2, 3, 7, 9])
    expected_graph = parse_tgf_graph(lines2textio(expected_graph_inputs))
    filtered_graph = filter_graph(graph, globs)
    assert_graph_equal(filtered_graph, expected_graph)


def test_example4_a_star():
    globs = ["a.*"]
    graph = copy.deepcopy(example4_graph)
    expected_graph_inputs = remove_indices(example4_input, [0, 3, 7, 10, 11, 15])
    expected_graph = parse_tgf_graph(lines2textio(expected_graph_inputs))
    filtered_graph = filter_graph(graph, globs)
    assert_graph_equal(filtered_graph, expected_graph)


def test_example4_a_h():
    globs = ["a.h"]
    graph = copy.deepcopy(example4_graph)
    expected_graph_inputs = remove_indices(example4_input, [3, 7, 10, 15])
    expected_graph = parse_tgf_graph(lines2textio(expected_graph_inputs))
    filtered_graph = filter_graph(graph, globs)
    assert_graph_equal(filtered_graph, expected_graph)


def test_example4_b_star():
    globs = ["b.*"]
    graph = copy.deepcopy(example4_graph)
    expected_graph_inputs = remove_indices(example4_input, [1, 5, 12, 13, 17, 18])
    expected_graph = parse_tgf_graph(lines2textio(expected_graph_inputs))
    filtered_graph = filter_graph(graph, globs)
    assert_graph_equal(filtered_graph, expected_graph)


def test_example4_b_h():
    globs = ["b.h"]
    graph = copy.deepcopy(example4_graph)
    expected_graph_inputs = remove_indices(example4_input, [5, 12, 17, 18])
    expected_graph = parse_tgf_graph(lines2textio(expected_graph_inputs))
    filtered_graph = filter_graph(graph, globs)
    assert_graph_equal(filtered_graph, expected_graph)


def test_example4_c_star():
    globs = ["c.*"]
    graph = copy.deepcopy(example4_graph)
    expected_graph_inputs = remove_indices(example4_input, [2, 6, 14])
    expected_graph = parse_tgf_graph(lines2textio(expected_graph_inputs))
    filtered_graph = filter_graph(graph, globs)
    assert_graph_equal(filtered_graph, expected_graph)


def test_example4_b_h():
    globs = ["b.h"]
    graph = copy.deepcopy(example4_graph)
    expected_graph_inputs = remove_indices(
        example4_input, [0, 1, 2, 3, 6, 7, 10, 11, 12, 13, 14, 15]
    )
    expected_graph = parse_tgf_graph(lines2textio(expected_graph_inputs))
    filtered_graph = filter_all_except(graph, globs)
    assert_graph_equal(filtered_graph, expected_graph)


def test_map_basenames_to_absolute():
    actual_mapping = map_basenames_to_absolute(example1_input)
    assert actual_mapping == example1_absolute_mapping


def test_shortest_unique_suffix_same_length():
    absolutes = {"/a/b/c.h", "/a/c/c.h"}
    expected = {"/a/b/c.h": "b/c.h", "/a/c/c.h": "c/c.h"}
    actual = shortest_unique_suffixes(absolutes)
    assert actual == expected


def test_shortest_unique_suffix_different_length():
    absolutes = {
        "/a/b/c/d/e.h",
        "/x/y/z/c/d/e.h",
    }
    expected = {
        "/a/b/c/d/e.h": "b/c/d/e.h",
        "/x/y/z/c/d/e.h": "z/c/d/e.h",
    }
    actual = shortest_unique_suffixes(absolutes)
    assert actual == expected


def test_shortest_unique_suffix_single_path():
    absolutes = {
        "/a/b/c.h",
    }
    expected = {"/a/b/c.h": "c.h"}
    actual = shortest_unique_suffixes(absolutes)
    assert actual == expected


def test_shotest_unique_suffix_all_different():
    absolutes = {
        "a/foo.h",
        "b/bar.h",
        "c/baz.h",
    }
    expected = {
        "a/foo.h": "foo.h",
        "b/bar.h": "bar.h",
        "c/baz.h": "baz.h",
    }
    actual = shortest_unique_suffixes(absolutes)
    assert actual == expected


def test_shorten_absolute_paths():
    actual_mapping = shorten_absolute_paths(example1_input)
    assert actual_mapping == example1_shortened_mapping
