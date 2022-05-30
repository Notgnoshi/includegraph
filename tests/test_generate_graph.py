import pprint

from includegraph import build_header_dependency_graph


def test_example1_cpp_graph(example1_src_example1_linemarkers):
    actual = build_header_dependency_graph(example1_src_example1_linemarkers)

    expected = {
        "/home/nots/Documents/includegraph/examples/example1/src/example1.cpp": {
            # TODO: Why is this missing bar.h? (was it already included?)
            "/home/nots/Documents/includegraph/examples/example1/include/example1/foo.h",
            "/home/nots/Documents/includegraph/examples/example1/src/private.h",
        },
        "/home/nots/Documents/includegraph/examples/example1/src/private.h": {
            "/home/nots/Documents/includegraph/examples/example1/src/circular.h",
        },
    }
    assert actual == expected


def test_example2_cpp_graph(example2_src_example2_linemarkers):
    actual = build_header_dependency_graph(example2_src_example2_linemarkers)

    expected = {
        "/home/nots/Documents/includegraph/examples/example2/src/example2.cpp": {
            # TODO: Why does this one have bar.h and example1 doesn't?
            "/home/nots/Documents/includegraph/examples/example2/include/example2/bar.h",
            "/home/nots/Documents/includegraph/examples/example2/include/example2/foo.h",
            "/home/nots/Documents/includegraph/examples/example2/src/private.h",
        },
        "/home/nots/Documents/includegraph/examples/example2/src/private.h": {
            "/home/nots/Documents/includegraph/examples/example2/src/circular.h",
        },
    }
    assert actual == expected


def test_example3_cpp_graph(example3_src_example3_linemarkers):
    actual = build_header_dependency_graph(example3_src_example3_linemarkers)

    expected = {
        "/home/nots/Documents/includegraph/examples/example3/src/example3.cpp": {
            "/home/nots/Documents/includegraph/examples/example3/include/example3/bar.h",
            "/home/nots/Documents/includegraph/examples/example3/include/example3/foo.h",
            "/home/nots/Documents/includegraph/examples/example3/src/private.h",
        },
        "/home/nots/Documents/includegraph/examples/example3/src/private.h": {
            "/home/nots/Documents/includegraph/examples/example3/src/circular.h",
        },
        "/home/nots/Documents/includegraph/examples/example3/src/circular.h": {
            "/home/nots/Documents/includegraph/examples/example3/src/private.h",
        },
    }
    assert actual == expected


# TODO: Add tests for system headers. How to make the tests manageable? (tree is WAY too big)
