from pprint import pprint

from includegraph import IncludeGraphNode, build_header_dependency_graph


def test_example1_cpp_graph(example1_src_example1_linemarkers):
    actual = build_header_dependency_graph(example1_src_example1_linemarkers, full_system=False)

    expected = {
        IncludeGraphNode(
            "/home/nots/Documents/includegraph/examples/example1/src/example1.cpp",
            is_source_file=True,
        ): {
            # TODO: Why is this missing bar.h? (was it already included?)
            IncludeGraphNode(
                "/home/nots/Documents/includegraph/examples/example1/src/private.h",
                is_source_file=False,
            ),
            IncludeGraphNode(
                "/home/nots/Documents/includegraph/examples/example1/include/example1/foo.h",
                is_source_file=False,
            ),
            IncludeGraphNode(
                "/usr/include/stdc-predef.h",
                is_source_file=False,
                is_system_header=True,
                is_first_level_system_header=True,
            ),
            IncludeGraphNode(
                "/usr/include/c++/11/iostream",
                is_source_file=False,
                is_system_header=True,
                is_first_level_system_header=True,
            ),
        },
        IncludeGraphNode(
            "/home/nots/Documents/includegraph/examples/example1/src/private.h",
            is_source_file=False,
        ): {
            IncludeGraphNode(
                "/home/nots/Documents/includegraph/examples/example1/src/circular.h",
                is_source_file=False,
            ),
            IncludeGraphNode(
                "/usr/include/c++/11/vector",
                is_source_file=False,
                is_system_header=True,
                is_first_level_system_header=True,
            ),
        },
        IncludeGraphNode(
            "/home/nots/Documents/includegraph/examples/example1/src/circular.h",
            is_source_file=False,
        ): {
            IncludeGraphNode(
                "/usr/include/c++/11/string",
                is_source_file=False,
                is_system_header=True,
                is_first_level_system_header=True,
            ),
        },
        IncludeGraphNode(
            "/home/nots/Documents/includegraph/examples/example1/include/example1/foo.h",
            is_source_file=False,
        ): set(),
        IncludeGraphNode(
            "/usr/include/c++/11/string",
            is_source_file=False,
            is_system_header=True,
            is_first_level_system_header=True,
        ): set(),
        IncludeGraphNode(
            "/usr/include/c++/11/vector",
            is_source_file=False,
            is_system_header=True,
            is_first_level_system_header=True,
        ): set(),
        IncludeGraphNode(
            "/usr/include/stdc-predef.h",
            is_source_file=False,
            is_system_header=True,
            is_first_level_system_header=True,
        ): set(),
        IncludeGraphNode(
            "/usr/include/c++/11/iostream",
            is_source_file=False,
            is_system_header=True,
            is_first_level_system_header=True,
        ): set(),
    }
    assert actual == expected


def test_example2_cpp_graph(example2_src_example2_linemarkers):
    actual = build_header_dependency_graph(example2_src_example2_linemarkers, full_system=False)

    expected = {
        IncludeGraphNode(
            "/home/nots/Documents/includegraph/examples/example2/src/example2.cpp",
            is_source_file=True,
        ): {
            # TODO: Why does this one have bar.h and example1 doesn't?
            IncludeGraphNode(
                "/home/nots/Documents/includegraph/examples/example2/include/example2/bar.h",
                is_source_file=False,
            ),
            IncludeGraphNode(
                "/home/nots/Documents/includegraph/examples/example2/include/example2/foo.h",
                is_source_file=False,
            ),
            IncludeGraphNode(
                "/home/nots/Documents/includegraph/examples/example2/src/private.h",
                is_source_file=False,
            ),
            IncludeGraphNode(
                "/usr/include/stdc-predef.h",
                is_source_file=False,
                is_system_header=True,
                is_first_level_system_header=True,
            ),
        },
        IncludeGraphNode(
            "/home/nots/Documents/includegraph/examples/example2/src/private.h",
            is_source_file=False,
        ): {
            IncludeGraphNode(
                "/home/nots/Documents/includegraph/examples/example2/src/circular.h",
                is_source_file=False,
            ),
        },
        IncludeGraphNode(
            "/home/nots/Documents/includegraph/examples/example2/include/example2/foo.h",
            is_source_file=False,
        ): set(),
        IncludeGraphNode(
            "/home/nots/Documents/includegraph/examples/example2/include/example2/bar.h",
            is_source_file=False,
        ): set(),
        IncludeGraphNode(
            filename="/home/nots/Documents/includegraph/examples/example2/src/circular.h",
            is_source_file=False,
        ): set(),
        IncludeGraphNode(
            "/usr/include/stdc-predef.h",
            is_source_file=False,
            is_system_header=True,
            is_first_level_system_header=True,
        ): set(),
    }
    assert actual == expected


def test_example3_cpp_graph(example3_src_example3_linemarkers):
    actual = build_header_dependency_graph(example3_src_example3_linemarkers, full_system=False)

    expected = {
        IncludeGraphNode(
            "/home/nots/Documents/includegraph/examples/example3/src/example3.cpp",
            is_source_file=True,
        ): {
            IncludeGraphNode(
                "/home/nots/Documents/includegraph/examples/example3/include/example3/bar.h",
                is_source_file=False,
            ),
            IncludeGraphNode(
                "/home/nots/Documents/includegraph/examples/example3/include/example3/foo.h",
                is_source_file=False,
            ),
            IncludeGraphNode(
                "/home/nots/Documents/includegraph/examples/example3/src/private.h",
                is_source_file=False,
            ),
            IncludeGraphNode(
                "/usr/include/stdc-predef.h",
                is_source_file=False,
                is_system_header=True,
                is_first_level_system_header=True,
            ),
        },
        IncludeGraphNode(
            "/home/nots/Documents/includegraph/examples/example3/src/private.h",
            is_source_file=False,
        ): {
            IncludeGraphNode(
                "/home/nots/Documents/includegraph/examples/example3/src/circular.h",
                is_source_file=False,
            ),
        },
        IncludeGraphNode(
            "/home/nots/Documents/includegraph/examples/example3/src/circular.h",
            is_source_file=False,
        ): {
            IncludeGraphNode(
                "/home/nots/Documents/includegraph/examples/example3/src/private.h",
                is_source_file=False,
            ),
        },
        IncludeGraphNode(
            "/home/nots/Documents/includegraph/examples/example3/include/example3/foo.h",
            is_source_file=False,
        ): set(),
        IncludeGraphNode(
            "/home/nots/Documents/includegraph/examples/example3/include/example3/bar.h",
            is_source_file=False,
        ): set(),
        IncludeGraphNode(
            "/usr/include/stdc-predef.h",
            is_source_file=False,
            is_system_header=True,
            is_first_level_system_header=True,
        ): set(),
    }
    assert actual == expected


# TODO: Add tests for system headers. How to make the tests manageable? (tree is WAY too big)
