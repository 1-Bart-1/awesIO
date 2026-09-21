"""Conformance tests for structure_schema.yml and the examples it is written for."""

import copy
import hashlib
import warnings
from pathlib import Path

import pytest

from awesio.validator import validate
from awesio.yaml import load_yaml

EXAMPLE_DIR = Path(__file__).parent.parent / "examples/structure"
EXAMPLES = sorted(EXAMPLE_DIR.glob("*.yml"))


@pytest.fixture(params=EXAMPLES, ids=lambda path: path.stem)
def structure(request):
    """Every .yml in examples/structure, so the invariants below cover all of them."""
    return load_yaml(request.param)


@pytest.fixture
def minimal():
    """The illustrative file, the only one holding every block at once."""
    return load_yaml(EXAMPLE_DIR / "minimal_structure.yml")


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


def connectivity_preimage(structure):
    """One-based row numbers, so zero-based readers do not disagree with the writer."""
    row_number = {row[0]: i + 1 for i, row in enumerate(structure["points"]["data"])}
    return f"{len(row_number)};" + "".join(
        f"{row_number[a]},{row_number[b]};"
        for _, (a, b), *_ in structure["segments"]["data"]
    )


def test_connectivity_sha_hashes_the_preimage(structure):
    digest = hashlib.sha256(connectivity_preimage(structure).encode()).hexdigest()
    assert digest == structure["metadata"]["connectivity_sha"]


def test_the_documented_preimage_is_the_minimal_example(minimal):
    assert connectivity_preimage(minimal) == "8;1,2;2,3;3,4;4,5;4,7;"


def test_n_points_agrees_with_the_points_block(structure):
    assert structure["metadata"]["n_points"] == len(structure["points"]["data"])


def test_wings_are_the_bodies_carrying_aero(structure):
    """There is no wings block; a wing is a body whose `aero` is not null."""
    wings = {row[0] for row in structure["bodies"]["data"] if row[2] is not None}
    assert wings, "every example describes a system that flies"
    assert {row[3] for row in structure["points"]["data"] if row[3]} <= wings


def test_the_minimal_example_has_two_wings(minimal):
    wings = [row[0] for row in minimal["bodies"]["data"] if row[2] is not None]
    assert wings == ["wing_left", "wing_right"]


def test_a_point_on_a_wing_names_that_wing_once(structure):
    """`wing` is null where `body` already is the wing the point belongs to."""
    wings = {row[0] for row in structure["bodies"]["data"] if row[2] is not None}
    for name, _, body, wing, _ in structure["points"]["data"]:
        assert not (body in wings and wing is not None), name


def test_every_reference_resolves_to_a_named_row(structure):
    def rows(block):
        return structure.get(block, {"data": []})["data"]

    def names(block):
        return {row[0] for row in rows(block)}

    points, segments, bodies = names("points"), names("segments"), names("bodies")
    for _, endpoints, *_ in rows("segments"):
        assert set(endpoints) <= points
    for _, pair, *_ in rows("pulleys"):
        assert set(pair) <= segments
    for _, _, members, *_ in rows("stations"):
        assert set(members) <= points
    for _, start, end, members in rows("tethers"):
        assert {start, end} <= points and set(members) <= segments
    for block in ("elastic_joints", "timoshenko_joints"):
        for _, pair, *_ in rows(block):
            assert set(pair) <= bodies


@pytest.mark.parametrize(
    "label, mutate",
    [
        ("reordered headers",
         lambda d: d["points"].update(
             headers=["type", "name", "body", "wing", "pos_cad"])),
        ("unknown dynamics type",
         lambda d: d["points"]["data"][0].__setitem__(1, "FLOATING")),
        ("two-component pos_cad",
         lambda d: d["points"]["data"][0].__setitem__(4, [0.0, 0.0])),
        ("a point's body given as an index",
         lambda d: d["points"]["data"][4].__setitem__(2, 2)),
        ("a segment with three endpoints",
         lambda d: d["segments"]["data"][0][1].append("tether_2")),
        ("negative segment length",
         lambda d: d["segments"]["data"][0].__setitem__(2, -1.0)),
        ("efficiency above one",
         lambda d: d["pulleys"]["data"].append(
             ["p1", ["seg_1", "seg_2"], "DYNAMIC", 1.4])),
        ("a station holding a bare point name",
         lambda d: d["stations"]["data"][0].__setitem__(2, "le_left")),
        ("a joint linking a point instead of a body",
         lambda d: d["elastic_joints"]["data"][0][1].__setitem__(1, None)),
        ("a joint with one anchor",
         lambda d: d["elastic_joints"]["data"][0][2].pop()),
        ("a two-component anchor offset",
         lambda d: d["timoshenko_joints"]["data"][0][2].__setitem__(0, [0.0, 2.0])),
        ("body offsets under the old body-frame suffix",
         lambda d: d["bodies"]["headers"].__setitem__(7, "com_offset_b")),
        ("negative axial rigidity",
         lambda d: d["timoshenko_joints"]["data"][0].__setitem__(3, -1.0)),
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
        ("missing segments block",
         lambda d: d.pop("segments")),
        ("a non-string appended header",
         lambda d: d["segments"]["headers"].append(42)),
        ("a row shorter than its appended headers",
         lambda d: d["segments"]["headers"].append("youngs_modulus")),
        ("a row longer than its headers",
         lambda d: d["segments"]["data"][0].append(1.1e11)),
        ("an undeclared key inside metadata",
         lambda d: d["metadata"].update(tool="SAM")),
        ("an undeclared key beside a table's headers and data",
         lambda d: d["segments"].update(units=["-"])),
    ],
)
def test_malformed_structures_are_rejected(minimal, label, mutate):
    broken = copy.deepcopy(minimal)
    mutate(broken)
    assert_invalid(broken)


def test_optional_blocks_may_be_absent(structure):
    """An absent optional block means the same as an empty one."""
    sparse = copy.deepcopy(structure)
    for block in ("stations", "pulleys", "tethers", "winches",
                  "bodies", "elastic_joints", "timoshenko_joints"):
        sparse.pop(block, None)
    for row in sparse["points"]["data"]:
        row[2] = row[3] = None
    assert_valid(sparse)


def test_a_reader_accepts_columns_appended_by_a_later_minor_version(structure):
    """Blocks are addressed by header, so appended columns must not break v0.1."""
    extended = copy.deepcopy(structure)
    extended["segments"]["headers"] += ["youngs_modulus"]
    for row in extended["segments"]["data"]:
        row += [1.1e11]
    assert_valid(extended)
