"""Conformance tests for structure_schema.yml and its worked example."""

import copy
import hashlib
import warnings
from pathlib import Path

import pytest

from awesio.validator import validate
from awesio.yaml import load_yaml

EXAMPLE = Path(__file__).parent.parent / "examples/structure/minimal_structure.yml"


@pytest.fixture
def structure():
    return load_yaml(EXAMPLE)


def assert_valid(data):
    """`validate` warns rather than raises, so a passing file must warn nothing."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        validate(data)


def assert_invalid(data):
    with pytest.warns(UserWarning, match="Validation failed"):
        validate(data)


def test_example_conforms(structure):
    assert_valid(structure)


def test_connectivity_sha_matches_its_documented_preimage(structure):
    """One-based row numbers, so zero-based readers do not disagree with the writer."""
    names = [row[0] for row in structure["points"]["data"]]
    preimage = f"{len(names)};" + "".join(
        f"{names.index(a) + 1},{names.index(b) + 1};"
        for _, a, b in structure["segments"]["data"]
    )
    assert preimage == "6;1,2;2,3;3,4;4,5;4,6;"
    digest = hashlib.sha256(preimage.encode()).hexdigest()
    assert digest == structure["metadata"]["connectivity_sha"]


def test_n_points_agrees_with_the_points_block(structure):
    assert structure["metadata"]["n_points"] == len(structure["points"]["data"])


@pytest.mark.parametrize(
    "label, mutate",
    [
        ("reordered headers",
         lambda d: d["points"].update(headers=["type", "name", "wing_idx", "pos_cad"])),
        ("unknown dynamics type",
         lambda d: d["points"]["data"][0].__setitem__(1, "FLOATING")),
        ("two-component pos_cad",
         lambda d: d["points"]["data"][0].__setitem__(3, [0.0, 0.0])),
        ("negative wing_idx",
         lambda d: d["points"]["data"][4].__setitem__(2, -1)),
        ("short segment row",
         lambda d: d["segments"]["data"][0].pop()),
        ("empty component name",
         lambda d: d["segments"]["data"][0].__setitem__(0, "")),
        ("tether segments given as indices",
         lambda d: d["tethers"]["data"][0].__setitem__(3, [1, 2, 3])),
        ("truncated connectivity_sha",
         lambda d: d["metadata"].update(connectivity_sha="abc")),
        ("uppercase connectivity_sha",
         lambda d: d["metadata"].update(connectivity_sha="A" * 64)),
        ("awesIO_version without a patch component",
         lambda d: d["metadata"].update(awesIO_version="0.1")),
        ("another schema's name",
         lambda d: d["metadata"].update(schema="system_schema.yml")),
        ("missing winches block",
         lambda d: d.pop("winches")),
        ("undeclared top-level block",
         lambda d: d.update(joints={"headers": [], "data": []})),
    ],
)
def test_malformed_structures_are_rejected(structure, label, mutate):
    broken = copy.deepcopy(structure)
    mutate(broken)
    assert_invalid(broken)


def test_a_reader_accepts_columns_appended_by_a_later_minor_version(structure):
    """Blocks are addressed by header, so appended columns must not break v0.1."""
    extended = copy.deepcopy(structure)
    extended["segments"]["headers"] += ["l0", "diameter", "model"]
    for row in extended["segments"]["data"]:
        row += [5.0, 0.004, "elastic"]
    assert_valid(extended)
