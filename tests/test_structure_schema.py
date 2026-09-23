"""Conformance tests for structure_schema.yml and the examples it is written for."""

import copy
import hashlib
import math
import re
import warnings
from pathlib import Path

import pytest

from awesio.validator import validate
from awesio.yaml import load_yaml

EXAMPLE_DIR = Path(__file__).parent.parent / "examples/structure"
EXAMPLES = sorted(EXAMPLE_DIR.glob("*.yml"))
SCHEMA = Path(__file__).parent.parent / "src/awesio/schemas/structure_schema.yml"
CONVENTIONS = Path(__file__).parent.parent / "docs/source/conventions.rst"


@pytest.fixture(params=EXAMPLES, ids=lambda path: path.stem)
def structure(request):
    """Every .yml in examples/structure, so the invariants below cover all of them."""
    return load_yaml(request.param)


@pytest.fixture
def beam():
    """The beam kite, the one example filling every block the cases below break."""
    return load_yaml(EXAMPLE_DIR / "v3_beam_structure.yml")


def rows(structure, block):
    """An absent optional block means the same as an empty one."""
    return structure.get(block, {"data": []})["data"]


def a_point_on_a_body(structure):
    """Most rows leave `body` null; breaking that column needs one that does not."""
    return next(row for row in rows(structure, "points") if row[2] is not None)


def append_column(table, header, value, unit=None):
    """Append a column to every row of `table`, leaving its units short without `unit`."""
    table["headers"].append(header)
    if unit is not None:
        table["units"].append(unit)
    for row in table["data"]:
        row.append(value)


def assert_valid(data):
    """`validate` warns rather than raises, so a passing file must warn nothing."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        validate(data)


def assert_invalid(data):
    with pytest.warns(UserWarning, match="Validation failed"):
        validate(data)


def connectivity_preimage(structure):
    """One-based row numbers, so zero-based readers do not disagree with the writer."""
    def section(named, paired):
        row_number = {row[0]: i + 1 for i, row in enumerate(rows(structure, named))}
        return f"{len(row_number)};" + "".join(
            f"{row_number[a]},{row_number[b]};"
            for _, (a, b), *_ in rows(structure, paired)
        )

    return section("points", "segments") + section("bodies", "tubes")


def test_connectivity_sha_hashes_the_preimage(structure):
    digest = hashlib.sha256(connectivity_preimage(structure).encode()).hexdigest()
    assert digest == structure["metadata"]["connectivity_sha"]


def test_the_documented_preimage_is_what_the_rule_produces():
    """The line `metadata.connectivity_sha` quotes, so the two cannot drift apart."""
    three_in_a_row = {"points": {"data": [["a"], ["b"], ["c"]]},
                      "segments": {"data": [["s1", ("a", "b")], ["s2", ("b", "c")]]},
                      "bodies": {"data": [["x"], ["y"]]},
                      "tubes": {"data": [["t1", ("x", "y")]]}}
    assert connectivity_preimage(three_in_a_row) == "3;1,2;2,3;2;1,2;"


def test_every_unit_the_schema_pins_is_spelled_on_the_conventions_page():
    units_section = CONVENTIONS.read_text().split("Units\n-----")[1].split("\n---")[0]
    listed = set(re.findall(r"\* - ``([^`]+)``", units_section))
    for name, block in load_yaml(SCHEMA)["properties"].items():
        for part in block.get("allOf", []):
            for item in part.get("properties", {}).get("units", {}).get("items", []):
                assert item["const"] in listed, name


def test_n_points_agrees_with_the_points_block(structure):
    assert structure["metadata"]["n_points"] == len(structure["points"]["data"])


def test_body_frames_are_unit_quaternions(structure):
    """Draft-07 can hold `Q_KA_to_ENU` to four numbers but not to unit length."""
    for name, _, _, frame, *_ in rows(structure, "bodies"):
        assert math.isclose(math.hypot(*frame), 1.0, abs_tol=1e-12), name


def test_body_inertia_is_symmetric(structure):
    """Draft-07 can hold `extra_inertia_KA` to three rows but not to symmetry."""
    for name, *_, inertia in rows(structure, "bodies"):
        for i in range(3):
            for j in range(i):
                assert inertia[i][j] == inertia[j][i], name


def ka_axes_in_enu(frame):
    """The KA x and y axes written in ENU: the first two columns of `Q_KA_to_ENU`."""
    w, x, y, z = frame
    return ([1 - 2 * (y * y + z * z), 2 * (x * y + w * z), 2 * (x * z - w * y)],
            [2 * (x * y - w * z), 1 - 2 * (x * x + z * z), 2 * (y * z + w * x)])


def direction(start, end):
    """Unit vector from `start` to `end`."""
    span = [end_i - start_i for start_i, end_i in zip(start, end)]
    return [component / math.hypot(*span) for component in span]


def wing_frame(beam):
    """`Q_KA_to_ENU` of the beam kite's wing, the body its canopy rides."""
    return next(row[3] for row in beam["bodies"]["data"] if row[1] == "KINEMATIC")


def test_the_wing_frame_follows_the_wings_own_edges(beam):
    """On a wing, KA x runs leading to trailing edge at mid-span, KA y tip to tip."""
    pos = {row[0]: row[3] for row in beam["points"]["data"]}

    def mid_span(edge):
        return [(a + b) / 2 for a, b in zip(pos[f"wing_{edge}_5"], pos[f"wing_{edge}_6"])]

    chord_axis, span_axis = ka_axes_in_enu(wing_frame(beam))
    for axis, (start, end) in (
            (chord_axis, (mid_span("le"), mid_span("te"))),
            (span_axis, (pos["wing_le_10"], pos["wing_le_1"]))):
        for got, want in zip(axis, direction(start, end)):
            assert math.isclose(got, want, abs_tol=1e-9)


def test_stations_run_from_the_left_tip_to_the_right(beam):
    """Station rows run from +y to -y of the wing's KA frame."""
    pos = {row[0]: row[3] for row in beam["points"]["data"]}
    _, span_axis = ka_axes_in_enu(wing_frame(beam))

    def spanwise(members):
        return sum(sum(a * b for a, b in zip(span_axis, pos[point])) for point in members)

    along_span = [spanwise(members) / len(members)
                  for *_, members in beam["stations"]["data"]]
    assert along_span == sorted(along_span, reverse=True)


def test_every_reference_resolves_to_a_named_row(structure):
    def names(block):
        return {row[0] for row in rows(structure, block)}

    points, segments, bodies = names("points"), names("segments"), names("bodies")
    for name, _, body, *_ in rows(structure, "points"):
        assert body is None or body in bodies, name
    for _, endpoints, *_ in rows(structure, "segments"):
        assert set(endpoints) <= points
    for _, pair, *_ in rows(structure, "pulleys"):
        assert set(pair) <= segments
    for _, _, members in rows(structure, "stations"):
        assert set(members) <= points
    for _, start, end, members in rows(structure, "tethers"):
        assert {start, end} <= points and set(members) <= segments
    for _, pair, *_ in rows(structure, "tubes"):
        assert set(pair) <= bodies


@pytest.mark.parametrize(
    "label, mutate",
    [
        ("reordered headers",
         lambda d: d["points"]["headers"].reverse()),
        ("points in the CAD frame",
         lambda d: d["points"]["headers"].__setitem__(3, "pos_CAD")),
        ("unknown dynamics type",
         lambda d: d["points"]["data"][0].__setitem__(1, "FLOATING")),
        ("two-component pos_ENU",
         lambda d: d["points"]["data"][0].__setitem__(3, [0.0, 0.0])),
        ("a point's body given as an index",
         lambda d: a_point_on_a_body(d).__setitem__(2, 2)),
        ("a point with negative extra mass",
         lambda d: d["points"]["data"][3].__setitem__(4, -8.4)),
        ("a point row without its drag coefficient",
         lambda d: d["points"]["data"][3].pop()),
        ("a segment with three endpoints",
         lambda d: d["segments"]["data"][0][1].append("tether_2")),
        ("negative segment length",
         lambda d: d["segments"]["data"][0].__setitem__(2, -1.0)),
        ("negative unit stiffness",
         lambda d: d["segments"]["data"][0].__setitem__(5, -1.0)),
        ("efficiency above one",
         lambda d: d["pulleys"]["data"].append(
             ["p1", ["seg_1", "seg_2"], "DYNAMIC", 1.4])),
        ("a station holding a bare point name",
         lambda d: d["stations"]["data"][0].__setitem__(2, "le_left")),
        ("a body inertia given as principal moments",
         lambda d: d["bodies"]["data"][0].__setitem__(5, [1.0, 1.0, 1.0])),
        ("a three-component body frame",
         lambda d: d["bodies"]["data"][0].__setitem__(3, [1.0, 0.0, 0.0])),
        ("a tube naming a null body",
         lambda d: d["tubes"]["data"][0][1].__setitem__(1, None)),
        ("a tube joining three bodies",
         lambda d: d["tubes"]["data"][0][1].append("kcu")),
        ("negative tube pressure",
         lambda d: d["tubes"]["data"][0].__setitem__(3, -1.0)),
        ("a tube whose law is a number",
         lambda d: d["tubes"]["data"][0].__setitem__(4, 42)),
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
         lambda d: d["metadata"].update(awesIO_version="1.0")),
        ("another schema's name",
         lambda d: d["metadata"].update(schema="system_schema.yml")),
        ("missing segments block",
         lambda d: d.pop("segments")),
        ("a non-string appended header",
         lambda d: d["segments"]["headers"].append(42)),
        ("a row shorter than its appended headers",
         lambda d: (d["segments"]["headers"].append("youngs_modulus"),
                    d["segments"]["units"].append("Pa"))),
        ("a row longer than its headers",
         lambda d: d["segments"]["data"][0].append(1.1e11)),
        ("an undeclared key inside metadata",
         lambda d: d["metadata"].update(tool="SAM")),
        ("an undeclared key beside a table's headers, units and data",
         lambda d: d["segments"].update(comment="bridle")),
        ("a table without its units",
         lambda d: d["segments"].pop("units")),
        ("a diameter in mm",
         lambda d: d["segments"]["units"].__setitem__(3, "mm")),
        ("a tube pressure in bar",
         lambda d: d["tubes"]["units"].__setitem__(3, "bar")),
        ("a required column without its unit",
         lambda d: d["points"]["units"].pop()),
        ("an appended column without its unit",
         lambda d: append_column(d["segments"], "youngs_modulus", 1.1e11)),
        ("an empty unit",
         lambda d: d["segments"]["units"].__setitem__(0, "")),
    ],
)
def test_malformed_structures_are_rejected(beam, label, mutate):
    broken = copy.deepcopy(beam)
    mutate(broken)
    assert_invalid(broken)


def test_optional_blocks_may_be_absent(structure):
    """An absent optional block means the same as an empty one."""
    sparse = copy.deepcopy(structure)
    for block in ("stations", "pulleys", "tethers", "winches", "bodies", "tubes"):
        sparse.pop(block, None)
    for row in sparse["points"]["data"]:
        row[2] = None
    assert_valid(sparse)


def test_a_reader_accepts_columns_appended_by_a_later_minor_version(structure):
    """Blocks are addressed by header, so appended columns must not break v1.0."""
    extended = copy.deepcopy(structure)
    append_column(extended["segments"], "youngs_modulus", 1.1e11, unit="Pa")
    assert_valid(extended)
