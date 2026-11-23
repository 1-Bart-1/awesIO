"""Conformance tests for structure_schema.yml and the examples it is written for."""

import hashlib
import math
import re
import shutil
import warnings
from pathlib import Path

import pytest
import ryml
import yaml

from awesio.validator import system_sha, validate
from awesio.yaml import load_yaml

EXAMPLE_DIR = Path(__file__).parent.parent / "examples/structure"
EXAMPLES = sorted(EXAMPLE_DIR.glob("*.yml"))
SYSTEM_EXAMPLES = sorted((EXAMPLE_DIR.parent / "system_config").glob("*.yml"))
V3_SYSTEM = EXAMPLE_DIR.parent / "system_config/v3_system.yml"
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


def records(structure, block):
    """The rows of a block as dictionaries by header."""
    table = structure.get(block, {"headers": [], "data": []})
    return [dict(zip(table["headers"], row)) for row in table["data"]]


def give_the_wing_a_canopy_material(structure, material):
    """Add the optional column to the first wing, holding `material`."""
    wings = structure["wings"]
    wings["headers"].append("canopy_material")
    wings["units"].append("-")
    wings["data"][0].append(material)


def a_point_on_a_body(structure):
    """Most rows leave `body` null; breaking that column needs one that does not."""
    return next(row for row in rows(structure, "points") if row[2] is not None)


def a_point_riding(structure, tube):
    """Return the first free point riding no tube, set to ride `tube`, adding a null
    `tube` column where there is none."""
    points = structure["points"]
    if "tube" not in points["headers"]:
        append_column(points, "tube", None, unit="-")
    column = points["headers"].index("tube")
    point = next(row for row in points["data"]
                 if row[2] is None and not row[1] and row[column] is None)
    point[column] = tube
    return point


def first_tube(structure):
    return rows(structure, "tubes")[0][0]


def first_body(structure):
    return rows(structure, "bodies")[0][0]


def set_column(table, header, value, unit):
    """Set the column under `header` to `value` in every row, appending it where absent."""
    if header not in table["headers"]:
        append_column(table, header, value, unit)
        return
    i = table["headers"].index(header)
    for row in table["data"]:
        row[i] = value


def append_column(table, header, value, unit=None):
    """Append a column to every row of `table`, leaving its units short without `unit`."""
    table["headers"].append(header)
    if unit is not None:
        table["units"].append(unit)
    for row in table["data"]:
        row.append(value)


def drop_column(table, header):
    """Remove the column under `header` from `table`, wherever it stands."""
    i = table["headers"].index(header)
    for row in [table["headers"], table["units"], *table["data"]]:
        del row[i]


def move_column_to_the_end(table, header):
    """Move the column under `header` behind every other, a tool's columns included."""
    i = table["headers"].index(header)
    for row in [table["headers"], table["units"], *table["data"]]:
        row.append(row.pop(i))


def append_header(table, header, unit):
    """Append a header and its unit to `table`, leaving every row one value short."""
    table["headers"].append(header)
    table["units"].append(unit)


def assert_valid(data, system=None):
    """`validate` warns rather than raises, so a passing file must warn nothing."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        validate(data, system=system)


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

    point_number = {row[0]: i + 1 for i, row in enumerate(rows(structure, "points"))}
    faces = rows(structure, "canopy_faces")
    corners = "".join(",".join(str(point_number[point]) for point in face[2]) + ";"
                      for face in faces)
    return (section("points", "segments") + section("bodies", "tubes")
            + f"{len(faces)};{corners}")


def test_connectivity_sha_hashes_the_preimage(structure):
    digest = hashlib.sha256(connectivity_preimage(structure).encode()).hexdigest()
    assert digest == structure["metadata"]["connectivity_sha"]


def test_the_documented_preimage_is_what_the_rule_produces():
    """The line `metadata.connectivity_sha` quotes, so the two cannot drift apart."""
    three_in_a_row = {"points": {"data": [["a"], ["b"], ["c"]]},
                      "segments": {"data": [["s1", ("a", "b")], ["s2", ("b", "c")]]},
                      "bodies": {"data": [["x"], ["y"]]},
                      "tubes": {"data": [["t1", ("x", "y")]]},
                      "canopy_faces": {"data": [["f1", "c", ["a", "b", "c"]]]}}
    assert connectivity_preimage(three_in_a_row) == "3;1,2;2,3;2;1,2;1;1,2,3;"


def test_every_unit_the_schema_pins_is_spelled_on_the_conventions_page():
    units_section = CONVENTIONS.read_text().split("Units\n-----")[1].split("\n---")[0]
    listed = set(re.findall(r"\* - ``([^`]+)``", units_section))
    for name, block in load_yaml(SCHEMA)["properties"].items():
        for part in block.get("allOf", []):
            for item in part.get("properties", {}).get("units", {}).get("items", []):
                assert item["const"] in listed, name
        for header, column in block.get("optionalColumns", {}).items():
            assert column["unit"] in listed, header


def test_n_points_agrees_with_the_points_block(structure):
    assert structure["metadata"]["n_points"] == len(structure["points"]["data"])


def test_body_and_wing_frames_are_unit_quaternions(structure):
    """Draft-07 can hold `Q_KA2ENU` to four numbers but not to unit length."""
    for block in ("bodies", "wings"):
        for name, _, frame, *_ in rows(structure, block):
            assert math.isclose(math.hypot(*frame), 1.0, abs_tol=1e-12), name


def test_body_inertia_is_symmetric(structure):
    """Draft-07 can hold `extra_inertia_KA` to three rows but not to symmetry."""
    for body in records(structure, "bodies"):
        inertia = body["extra_inertia_KA"]
        for i in range(3):
            for j in range(i):
                assert inertia[i][j] == inertia[j][i], body["name"]


def direction(start, end):
    """Unit vector from `start` to `end`."""
    span = [end_i - start_i for start_i, end_i in zip(start, end)]
    return [component / math.hypot(*span) for component in span]


def test_every_point_is_joined_to_the_rest(structure):
    """Segments, canopy faces, the body or tube a point rides and tubes make the example one
    mechanism."""
    neighbours = {}

    def join(*names):
        for name in names:
            neighbours.setdefault(name, set()).update(names)

    tube_bodies = {tube["name"]: tube["bodies"] for tube in records(structure, "tubes")}
    for point in records(structure, "points"):
        ridden = [point["body"]] if point.get("body") else tube_bodies.get(point.get("tube"), [])
        join(point["name"], *(("body", body) for body in ridden))
    for _, endpoints, *_ in rows(structure, "segments"):
        join(*endpoints)
    for bodies in tube_bodies.values():
        join(*(("body", body) for body in bodies))
    for *_, corners in rows(structure, "canopy_faces"):
        join(*corners)
    reached, frontier = set(), [structure["points"]["data"][0][0]]
    while frontier:
        name = frontier.pop()
        if name not in reached:
            reached.add(name)
            frontier.extend(neighbours[name])
    assert {row[0] for row in rows(structure, "points")} <= reached


def test_stations_run_from_the_left_tip_to_the_right(beam):
    """Station rows run from the left wing tip to the right."""
    pos = {row[0]: row[3] for row in beam["points"]["data"]}
    span_axis = direction(pos["wing_le_10"], pos["wing_le_1"])

    def spanwise(members):
        return sum(sum(a * b for a, b in zip(span_axis, pos[point])) for point in members)

    along_span = [spanwise(station["points"]) / len(station["points"])
                  for station in records(beam, "spanwise_stations")]
    assert along_span == sorted(along_span, reverse=True)


def test_every_reference_resolves_to_a_named_row(structure):
    def names(block):
        return {row[0] for row in rows(structure, block)}

    points, segments, bodies = names("points"), names("segments"), names("bodies")
    for name, _, body, *_ in rows(structure, "points"):
        assert body is None or body in bodies, name
    for name, endpoints, *_ in rows(structure, "segments"):
        assert set(endpoints) <= points, name
    for _, pair, *_ in rows(structure, "pulleys"):
        assert set(pair) <= segments
    for station in records(structure, "spanwise_stations"):
        assert station["wing"] in names("wings"), station["name"]
        assert set(station["points"]) <= points, station["name"]
    for tether in records(structure, "tethers"):
        assert {tether["start_point"], tether["end_point"]} <= points
        assert set(tether["segments"]) <= segments
    for name, pair, *_ in rows(structure, "tubes"):
        assert set(pair) <= bodies, name
    without_a_canopy = {wing["name"] for wing in records(structure, "wings")
                        if "canopy_material" in wing and wing["canopy_material"] is None}
    for name, wing, corners, *_ in rows(structure, "canopy_faces"):
        assert wing in names("wings") - without_a_canopy and set(corners) <= points, name


@pytest.mark.parametrize(
    "label, mutate",
    [
        ("reordered headers",
         lambda d: d["points"]["headers"].reverse()),
        ("points in the CAD frame",
         lambda d: d["points"]["headers"].__setitem__(3, "pos_CAD")),
        ("a point's fixed flag given as a solver's dynamics type",
         lambda d: d["points"]["data"][0].__setitem__(1, "STATIC")),
        ("a point both held in the world and on a body",
         lambda d: a_point_on_a_body(d).__setitem__(1, True)),
        ("a point's tube given as an index",
         lambda d: a_point_riding(d, 0)),
        ("a body's fixed flag given as a solver's dynamics type",
         lambda d: append_column(d["bodies"], "fixed", "STATIC", unit="-")),
        ("two-component pos_ENU",
         lambda d: d["points"]["data"][0].__setitem__(3, [0.0, 0.0])),
        ("a point's body given as an index",
         lambda d: a_point_on_a_body(d).__setitem__(2, 2)),
        ("a point with negative extra mass",
         lambda d: d["points"]["data"][3].__setitem__(4, -8.4)),
        ("a point row without its extra mass",
         lambda d: d["points"]["data"][3].pop()),
        ("a segment with three endpoints",
         lambda d: d["segments"]["data"][0][1].append("tether_2")),
        ("negative segment length",
         lambda d: d["segments"]["data"][0].__setitem__(2, -1.0)),
        ("a segment's material given as a number",
         lambda d: d["segments"]["data"][0].__setitem__(4, 970.0)),
        ("a station holding a bare point name",
         lambda d: d["spanwise_stations"]["data"][0].__setitem__(2, "le_left")),
        ("a station without its wing",
         lambda d: d["spanwise_stations"]["data"][0].__setitem__(1, None)),
        ("a body inertia given as principal moments",
         lambda d: d["bodies"]["data"][0].__setitem__(4, [1.0, 1.0, 1.0])),
        ("a three-component body frame",
         lambda d: d["bodies"]["data"][0].__setitem__(2, [1.0, 0.0, 0.0])),
        ("a tube naming a null body",
         lambda d: d["tubes"]["data"][0][1].__setitem__(1, None)),
        ("a tube joining three bodies",
         lambda d: d["tubes"]["data"][0][1].append("kcu")),
        ("negative tube pressure",
         lambda d: d["tubes"]["data"][0].__setitem__(3, -1.0)),
        ("a tube's material given as a number",
         lambda d: d["tubes"]["data"][0].__setitem__(4, 42)),
        ("short segment row",
         lambda d: d["segments"]["data"][0].pop()),
        ("empty component name",
         lambda d: d["segments"]["data"][0].__setitem__(0, "")),
        ("a tether placed at a negative length",
         lambda d: set_column(d["tethers"], "init_stretched_length", -1.0, "m")),
        ("a tether placed in compression",
         lambda d: set_column(d["tethers"], "init_tether_force", -1.0, "N")),
        ("a tether's rest length a negative fraction of its placed length",
         lambda d: set_column(d["tethers"], "init_stretch_frac", -0.5, "-")),
        ("tether segments given as indices",
         lambda d: d["tethers"]["data"][0].__setitem__(3, [1, 2, 3])),
        ("a winch without its drum radius",
         lambda d: d["winches"]["data"][0].pop()),
        ("a negative winch gear ratio",
         lambda d: d["winches"]["data"][0].__setitem__(3, -1.0)),
        ("missing connectivity_sha",
         lambda d: d["metadata"].pop("connectivity_sha")),
        ("truncated connectivity_sha",
         lambda d: d["metadata"].update(connectivity_sha="abc")),
        ("uppercase connectivity_sha",
         lambda d: d["metadata"].update(connectivity_sha="A" * 64)),
        ("missing system",
         lambda d: d["metadata"].pop("system")),
        ("missing system_sha",
         lambda d: d["metadata"].pop("system_sha")),
        ("truncated system_sha",
         lambda d: d["metadata"].update(system_sha="abc")),
        ("awesIO_version without a patch component",
         lambda d: d["metadata"].update(awesIO_version="1.0")),
        ("another schema's name",
         lambda d: d["metadata"].update(schema="system_schema.yml")),
        ("missing segments block",
         lambda d: d.pop("segments")),
        ("a non-string appended header",
         lambda d: d["segments"]["headers"].append(42)),
        ("a header given twice",
         lambda d: append_column(d["segments"], "name", "seg", unit="-")),
        ("a negative diameter behind a tool's column",
         lambda d: (append_column(d["segments"], "damping_per_stiffness", 0.002, unit="s"),
                    move_column_to_the_end(d["segments"], "diameter"),
                    d["segments"]["data"][0].__setitem__(-1, -0.004))),
        ("a rest length in mm behind a tool's column",
         lambda d: (append_column(d["segments"], "damping_per_stiffness", 0.002, unit="s"),
                    move_column_to_the_end(d["segments"], "rest_length"),
                    d["segments"]["units"].__setitem__(-1, "mm"))),
        ("a row shorter than its appended headers",
         lambda d: append_header(d["segments"], "damping_per_stiffness", "s")),
        ("a row longer than its headers",
         lambda d: d["segments"]["data"][0].append(0.002)),
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
         lambda d: append_column(d["segments"], "damping_per_stiffness", 0.002)),
        ("an appended column with an empty unit",
         lambda d: append_column(d["segments"], "damping_per_stiffness", 0.002, unit="")),
        ("a canopy face with two corners",
         lambda d: d["canopy_faces"]["data"][0][2].__delitem__(slice(2))),
        ("a canopy face with a repeated corner",
         lambda d: d["canopy_faces"]["data"][0][2].__setitem__(
             1, d["canopy_faces"]["data"][0][2][0])),
        ("a segment from a point to itself",
         lambda d: d["segments"]["data"][0][1].__setitem__(
             1, d["segments"]["data"][0][1][0])),
        ("a canopy face with five corners",
         lambda d: d["canopy_faces"]["data"][0][2].append("wing_le_8")),
        ("a canopy material given as a number",
         lambda d: give_the_wing_a_canopy_material(d, 42)),
        ("a canopy face without its wing",
         lambda d: d["canopy_faces"]["data"][0].__setitem__(1, None)),
        ("a wing without its origin", lambda d: drop_column(d["wings"], "pos_ENU")),
        ("a wing without its frame", lambda d: drop_column(d["wings"], "Q_KA2ENU")),
        ("a wing origin in millimetres",
         lambda d: d["wings"]["units"].__setitem__(1, "mm")),
        ("a wing's body given as an index",
         lambda d: append_column(d["wings"], "body", 0, unit="-")),
        ("a wing frame of three numbers",
         lambda d: d["wings"]["data"][0][2].pop()),
    ],
)
def test_malformed_structures_are_rejected(beam, label, mutate):
    mutate(beam)
    assert_invalid(beam)


def test_optional_blocks_may_be_absent(structure):
    """An absent optional block means the same as an empty one."""
    for block in ("spanwise_stations", "pulleys", "tethers", "winches",
                  "bodies", "tubes", "wings", "canopy_faces"):
        structure.pop(block, None)
    for row in structure["points"]["data"]:
        row[2] = None
    assert_valid(structure)


def test_the_core_alone_is_a_valid_structure(structure):
    """Every column a block does not require may be left out, materials and all."""
    for name, block in load_yaml(SCHEMA)["properties"].items():
        for header in block.get("optionalColumns", {}):
            if name in structure and header in structure[name]["headers"]:
                drop_column(structure[name], header)
    if "pulleys" in structure:
        drop_column(structure["pulleys"], "efficiency")
    assert_valid(structure)


def test_a_free_point_may_ride_a_named_tube(beam):
    a_point_riding(beam, first_tube(beam))
    assert_valid(beam)


def test_a_body_may_be_held_in_the_world(beam):
    append_column(beam["bodies"], "fixed", True, unit="-")
    assert_valid(beam)


def test_a_tether_may_say_how_it_is_placed(beam):
    set_column(beam["tethers"], "init_stretched_length", 250.0, "m")
    set_column(beam["tethers"], "init_tether_force", 0.0, "N")
    set_column(beam["tethers"], "init_stretch_frac", 1.0, "-")
    assert_valid(beam)


def test_a_wing_may_name_the_body_it_moves_with(beam):
    set_column(beam["wings"], "body", first_body(beam), unit="-")
    assert_valid(beam)


def test_a_wing_may_have_no_canopy(structure):
    wings = structure["wings"]
    if "canopy_material" in wings["headers"]:
        wings["data"][0][wings["headers"].index("canopy_material")] = None
    structure.pop("canopy_faces", None)
    assert_valid(structure)


def test_a_reader_accepts_columns_appended_by_a_later_minor_version(structure):
    """Blocks are addressed by header, so appended columns must not break v1.0."""
    append_column(structure["segments"], "added_in_a_later_minor_version", 0.002, unit="s")
    assert_valid(structure)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda path: path.stem)
def test_every_structure_validates_with_its_system_file(path):
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        validate(path)


def tether_segments(structure):
    """The beam's tether segments, as rows of its segments block."""
    [tether] = records(structure, "tethers")
    return [row for row in rows(structure, "segments") if row[0] in tether["segments"]]


def scalars(node, kind=str):
    """Every value of type `kind` under `node`, at any depth; booleans are no integers."""
    if isinstance(node, dict):
        return [scalar for value in node.values() for scalar in scalars(value, kind)]
    if isinstance(node, list):
        return [scalar for value in node for scalar in scalars(value, kind)]
    return [node] if isinstance(node, kind) and not isinstance(node, bool) else []


def with_system(tmp_path, structure, edit_system=lambda system: None):
    """Validate `structure` against an edited copy of the V3 system, its hash recomputed."""
    system = load_yaml(V3_SYSTEM)
    edit_system(system)
    path = tmp_path / "system.yml"
    path.write_text(yaml.safe_dump(system))
    structure["metadata"]["system_sha"] = system_sha(path)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", UserWarning)
        validate(structure, system=path)
    return " ".join(str(warning.message) for warning in caught)


def test_an_unedited_system_passes_the_checks_below(tmp_path, beam):
    """So each failure below is the failure its edit made, not the helper's."""
    assert with_system(tmp_path, beam) == ""


def test_a_segment_material_the_system_lacks_is_refused(tmp_path, beam):
    beam["segments"]["data"][0][4] = "unobtainium"
    assert "names material 'unobtainium'" in with_system(tmp_path, beam)


def test_a_tube_material_the_system_lacks_is_refused(tmp_path, beam):
    beam["tubes"]["data"][0][4] = "unobtainium"
    assert "names material 'unobtainium'" in with_system(tmp_path, beam)


def test_a_canopy_material_the_system_lacks_is_refused(tmp_path, beam):
    give_the_wing_a_canopy_material(beam, "unobtainium")
    assert "names material 'unobtainium'" in with_system(tmp_path, beam)


def test_a_tether_the_system_lacks_is_refused(tmp_path, beam):
    beam["tethers"]["data"][0][0] = "kite_string"
    assert "tether 'kite_string' is not in the system" in with_system(tmp_path, beam)


def test_a_tether_segment_giving_the_diameter_its_tether_owns_is_refused(tmp_path, beam):
    tether_segments(beam)[0][3] = 0.004
    assert "gives a diameter" in with_system(tmp_path, beam)


def test_a_tether_segment_of_another_material_is_refused(tmp_path, beam):
    tether_segments(beam)[0][4] = "dyneema"
    assert "names material 'dyneema', the system says" in with_system(tmp_path, beam)


def test_a_tether_naming_a_segment_the_structure_lacks_is_refused(tmp_path, beam):
    beam["tethers"]["data"][0][3].append("no_such_segment")
    assert "names segment 'no_such_segment'" in with_system(tmp_path, beam)


def test_a_tether_defined_twice_in_the_system_is_refused(tmp_path, beam):
    def with_a_second_copy(system):
        system["components"]["tethers"].append(dict(system["components"]["tethers"][0]))

    assert "is defined twice" in with_system(tmp_path, beam, with_a_second_copy)


def test_tether_rest_lengths_must_add_up_to_its_length(tmp_path, beam):
    tether_segments(beam)[0][2] += 1.0
    assert "segments add up to 251" in with_system(tmp_path, beam)


def test_a_system_edited_after_the_structure_was_written_is_refused(tmp_path, beam):
    system = tmp_path / "system.yml"
    system.write_text(V3_SYSTEM.read_text() + "# edited\n")
    with pytest.warns(UserWarning, match="hashes to"):
        validate(beam, system=system)


def a_system_including(tmp_path, materials):
    """The V3 system with its materials moved to a file it pulls in with `!include`."""
    system = load_yaml(V3_SYSTEM)
    (tmp_path / "materials.yml").write_text(yaml.safe_dump(materials))
    system["materials"] = "INCLUDE"
    path = tmp_path / "system.yml"
    path.write_text(yaml.safe_dump(system).replace("INCLUDE", "!include materials.yml"))
    return path


def test_a_system_without_includes_hashes_as_its_bytes():
    assert system_sha(V3_SYSTEM) == hashlib.sha256(V3_SYSTEM.read_bytes()).hexdigest()


def test_the_system_hash_covers_the_files_it_includes(tmp_path):
    path = a_system_including(tmp_path, load_yaml(V3_SYSTEM)["materials"])
    expected = hashlib.sha256(path.read_bytes() + (tmp_path / "materials.yml").read_bytes())
    assert system_sha(path) == expected.hexdigest()


def test_a_file_the_system_includes_edited_after_the_structure_is_refused(tmp_path, beam):
    materials = load_yaml(V3_SYSTEM)["materials"]
    path = a_system_including(tmp_path, materials)
    beam["metadata"]["system_sha"] = system_sha(path)
    assert_valid(beam, system=path)
    materials[0]["parameters"]["density"] *= 2
    (tmp_path / "materials.yml").write_text(yaml.safe_dump(materials))
    with pytest.warns(UserWarning, match="hashes to"):
        validate(beam, system=path)


def test_no_example_refers_to_a_row_by_its_number(structure):
    """No column of the schema holds an integer, so one in any column is a row number."""
    tables = [block for block in structure.values() if "data" in block]
    assert not [value for table in tables for row in table["data"]
                for value in scalars(row, int)]


def test_a_structure_naming_a_system_file_that_is_not_there_is_refused(tmp_path):
    structure = shutil.copy(EXAMPLE_DIR / "v3_beam_structure.yml", tmp_path)
    with pytest.warns(UserWarning, match="not found"):
        validate(structure)


def test_an_invalid_system_file_is_refused_with_its_structure(tmp_path, beam):
    def without_components(system):
        system.pop("components")

    assert "'components' is a required property" in with_system(
        tmp_path, beam, without_components)


def test_a_document_that_is_not_a_system_is_refused_as_its_system(tmp_path, beam):
    other = Path(shutil.copy(EXAMPLE_DIR / "v3_psm_structure.yml", tmp_path))
    beam["metadata"]["system_sha"] = system_sha(other)
    with pytest.warns(UserWarning, match="required property"):
        validate(beam, system=other)


@pytest.mark.parametrize("path", [*EXAMPLES, *SYSTEM_EXAMPLES], ids=lambda path: path.stem)
def test_a_strict_yaml_1_2_reader_loads_the_examples(path):
    """rapidyaml refuses a bare `-`, which ruamel.yaml and PyYAML let through."""
    ryml.parse_in_arena(path.read_text())


@pytest.mark.parametrize("path", [*EXAMPLES, *SYSTEM_EXAMPLES], ids=lambda path: path.stem)
def test_every_number_reads_as_a_number_in_pyyaml(path):
    """PyYAML reads an exponent lacking a dot or a sign, such as `1e-12`, as a string."""
    number = re.compile(r"[-+]?(\.\d+|\d+(\.\d*)?)[eE][-+]?\d+$")
    assert not [text for text in scalars(yaml.safe_load(path.read_text()))
                if number.match(text)]
