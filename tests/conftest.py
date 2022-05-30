from pathlib import Path
from typing import Dict, Iterable

import pytest

from includegraph import LINEMARKER_PATTERN, parse_linemarkers_from_match


def load_linemarkers(path: Path) -> Iterable[Dict]:
    """Get linemarkers from disk.

    {
        "linenumber": str,
        "filename": str,
        "flags": List[int],
    }
    """
    with path.open("rb") as f:
        for line in f:
            match = LINEMARKER_PATTERN.match(line)
            if match is not None:
                linemarker = parse_linemarkers_from_match(match)
                yield linemarker


def get_example_path(example: str) -> Path:
    path = Path(__file__).parent.parent / example
    assert path.exists()
    return path


def load_example_linemarkers(example: str) -> Iterable[Dict]:
    path = get_example_path(example)
    return load_linemarkers(path)


@pytest.fixture
def example1_src_example1_linemarkers():
    return load_example_linemarkers("examples/example1/src/example1.cpp.txt")


@pytest.fixture
def example2_src_example2_linemarkers():
    return load_example_linemarkers("examples/example2/src/example2.cpp.txt")


@pytest.fixture
def example3_src_example3_linemarkers():
    return load_example_linemarkers("examples/example3/src/example3.cpp.txt")
