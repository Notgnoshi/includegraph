import io

from tgf2graphviz import IncludeGraphNode, parse_tgf_edge_list, parse_tgf_graph, parse_tgf_node_list

example2_nodes_expected = [
    IncludeGraphNode(filename="src/example2.cpp"),
    IncludeGraphNode(
        filename="/usr/include/stdc-predef.h",
        is_source_file=False,
        is_system_header=True,
        is_first_level_system_header=True,
    ),
    IncludeGraphNode(filename="include/example2/foo.h", is_source_file=False),
    IncludeGraphNode(filename="include/example2/bar.h", is_source_file=False),
    IncludeGraphNode(filename="src/private.h", is_source_file=False),
    IncludeGraphNode(filename="src/circular.h", is_source_file=False),
]
example2_node_input = [
    '"src/example2.cpp"	"is_source_file=True, is_system_header=False, is_first_level_system_header=False"',
    '"/usr/include/stdc-predef.h"	"is_source_file=False, is_system_header=True, is_first_level_system_header=True"',
    '"include/example2/foo.h"	"is_source_file=False, is_system_header=False, is_first_level_system_header=False"',
    '"include/example2/bar.h"	"is_source_file=False, is_system_header=False, is_first_level_system_header=False"',
    '"src/private.h"	"is_source_file=False, is_system_header=False, is_first_level_system_header=False"',
    '"src/circular.h"	"is_source_file=False, is_system_header=False, is_first_level_system_header=False"',
    "#",
]
example2_edges_input = [
    '"src/example2.cpp" "include/example2/bar.h"',
    '"src/example2.cpp" "src/private.h"',
    '"src/example2.cpp" "include/example2/foo.h"',
    '"src/example2.cpp" "/usr/include/stdc-predef.h"',
    '"src/private.h" "src/circular.h"',
]
example2_edges_expected = [
    (example2_nodes_expected[0], example2_nodes_expected[3]),
    (example2_nodes_expected[0], example2_nodes_expected[4]),
    (example2_nodes_expected[0], example2_nodes_expected[2]),
    (example2_nodes_expected[0], example2_nodes_expected[1]),
    (example2_nodes_expected[4], example2_nodes_expected[5]),
]
example2_input = example2_node_input + example2_edges_input
example2_expected = {
    example2_nodes_expected[0]: {
        example2_nodes_expected[3],
        example2_nodes_expected[4],
        example2_nodes_expected[2],
        example2_nodes_expected[1],
    },
    example2_nodes_expected[1]: set(),
    example2_nodes_expected[2]: set(),
    example2_nodes_expected[3]: set(),
    example2_nodes_expected[4]: set([example2_nodes_expected[5]]),
    example2_nodes_expected[5]: set(),
}


def test_parse_nodes_stops_at_marker():
    lines = iter(example2_input)
    nodes = parse_tgf_node_list(lines)
    nodes = list(nodes)  # need to exhaust the generator
    next_line = next(lines)
    assert next_line == example2_edges_input[0]


def test_parse_nodes():
    lines = iter(example2_node_input)
    nodes = parse_tgf_node_list(lines)
    nodes = list(nodes)
    assert nodes == example2_nodes_expected


def test_parse_edges():
    lines = iter(example2_edges_input)
    nodes = {}
    for node in example2_nodes_expected:
        nodes[node.filename] = node
    edges = parse_tgf_edge_list(lines, nodes)
    edges = list(edges)
    assert edges == example2_edges_expected


def test_parse_graph():
    buffer = "\n".join(example2_input).encode("utf-8")
    lines = io.TextIOWrapper(io.BytesIO(buffer))
    graph = parse_tgf_graph(lines)
    assert graph == example2_expected
