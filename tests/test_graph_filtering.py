from pathlib import PurePath

from filtergraph import map_basenames_to_absolute, shorten_absolute_paths, shortest_unique_suffixes

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
