AWE System Structure Schema
===========================

The structure schema describes the **resolved structural definition** of an AWE
system: the points, the segments, stations, pulleys, tethers and winches built on
them, the rigid bodies, and the tubes between those bodies. Each component carries
its own geometry and material, so a conforming file is a complete structural
definition rather than a connectivity sketch.

It is the layer :doc:`system_schema` leaves free-form — its ``wing_sections``,
``bridle_nodes``, ``bridle_lines`` and ``bridle_connections`` blocks are bare
``type: object`` under ``additionalProperties: true``, so today any content
validates.

Plotting is the clearest symptom of not having it. Two tools cannot draw each other's
system because neither can describe it, so every viewer is written against one model.
With a shared structure, drawing a state is one code path and every model gets every
viewer.

.. note::
   All quantities follow the SI unit convention used throughout awesIO.

Canonical form only
-------------------

A conforming file is **fully resolved and expanded**: no variable substitution block,
no segment counts left to expand, every component explicit. It is readable with
nothing beyond a YAML or JSON parser.

Authoring dialects — multi-variable substitution, tether expansion, defaults — stay
profiles of the tool that defines them and *emit* canonical files. An interchange
format is worth having only if any tool can read it, and requiring implementers to
build a substitution engine before they can load a file is an adoption barrier.
Draft-07 could not express an authoring layer in any case: a row whose arity depends
on a variables block has no vocabulary in JSON Schema.

Tables, not nesting
-------------------

Every block is a ``headers``/``data`` table and every reference is by name, so a file
reads as a spreadsheet and rows reorder without rewriting indices:

.. code-block:: yaml

   segments:
     headers: [name, points, l0, diameter, density, unit_stiffness]
     data:
       - [seg_1, [ground, tether_1], 10.0, 0.004, 724.0, 614600.0]

What an element connects is one column holding a two-element tuple — a segment's
``points``, a pulley's ``segments``, a tube's ``bodies`` — so the schema fixes that
there are exactly two.

A block may carry columns beyond the ones the schema requires. **A reader addresses
columns by header, never by position** — that is what lets a later minor version
append a column without breaking an older reader. Every header is a string and every
row is exactly as long as its headers; the ``table`` definition states the latter as
``rowsMatchHeaders``, a keyword ``awesio.validator`` enforces and other draft-07
validators skip. An absent optional block means the same as an empty one; only
``metadata``, ``points`` and ``segments`` are required.

YAML and JSON are two encodings of one model. JSON is the machine encoding, and it
travels in the table-level metadata of an Arrow state log under the key ``topology``,
which is what makes a log self-describing: plotting it needs no sidecar file.

The core, and what a tool carries beside it
-------------------------------------------

**What the schema requires is what a viewer and every solver need, and nothing that
only one tool needs.** A column earns its place in the core by having a second reader
that cannot do without it; the test is a reader outside the tool the column came
from, not whether the quantity is respectable.

That is why a tube gives its ``diameter`` and ``pressure`` rather than its ``EA``,
``GA``, ``GJ``, ``EIy`` and ``EIz``: a finite-element reader re-derives those as the
tube deforms, so a file that states them has already committed to one solver's
linearisation.

A tool carries the rest of its own data beside the core as extra columns and as extra
top-level blocks of any shape — SAM's ``wings``, ``transforms`` and ``groups``, and
its choice of model wherever it has one. ``metadata`` and a table's own keys stay
closed. **A reader ignores every column and block it does not know.** A later minor
version may claim any such name for the schema, after which the tool renames its own.

Stations are not aerodynamic sections
-------------------------------------

A **station** is a group of points sharing one twist degree of freedom. It is a
structural group, and it is coarser than the aerodynamic mesh: a wing meshed at forty
panels may carry four stations, each spanning ten of them.

The distinction is worth stating because conflating the two is a mistake that has
already been made and fixed once in a reference implementation, where a station count
was passed as a section count and produced a four-section wing. A reader that builds
a lifting surface by pairing adjacent station rows will draw the wrong shape. Station
rows carry no spanwise ordering guarantee and none should be assumed.

Bodies, and the tubes between them
----------------------------------

A rigid body has a position and a frame: ``pos_CAD`` is its origin, which is its
centre of mass, and ``Q_KA_to_CAD`` the rotation from its own KA frame into CAD.
``mass`` and ``inertia_principal`` are taken about that origin and **already include
the points fixed to the body**, so a reader takes the body row as it stands rather
than deriving it from those points or adding them to it again. A tool that carries no
rotational inertia writes zeros.

A point carries its own ``mass``, not counting the segments attached to it, and the
``drag_area`` its ``drag_coefficient`` refers to. ``body`` is the rigid body a
``BODY_STATIC`` point is fixed to, and is null for a point that belongs to none.

**A tube joins two bodies**, named in its ``bodies`` column and never as points. It is
straight and one ``diameter`` holds for the whole element, so a curved or tapered tube
is a chain of them and its rest length follows from where its two bodies sit. What it
carries besides its geometry is ``pressure`` and ``law``, the name of the stiffness
law a reader derives the element's rigidities from — nonlinearly as the tube deforms,
or linearised about the undeformed tube, as that reader chooses. How a law is
parameterised is not yet part of this schema, so a file naming one is portable only
between readers that know the name. A segment's ``unit_stiffness`` takes the same
freedom: a number is the linear value, a string names a law.

One table serves a finite-element beam element and a six-degree-of-freedom elastic
link alike: they differ in how a solver assembles them, not in what a document has to
say about the tube. The discretisation is carried by how many bodies a writer puts
along it — one tube where a beam model has one element, six where a finite-element
mesh has six, both describing the same kite.

Versioning
----------

The ``metadata`` block carries two fields that are easy to confuse:

``schema``
   Pinned by ``const`` to the filename, awesIO's convention. It identifies *which*
   schema, never which version.

``awesIO_version``
   The version. **A reader must refuse an unknown major version and warn on an
   unknown minor one.** Every implementation applies that one rule, so a breaking
   change is caught at load rather than silently misread.

``connectivity_sha`` guards the pairing of a structure with a state log. Its preimage
is ASCII and built in document order, in two sections: the point count, then each
segment's two endpoints as **one-based** row numbers into the points block; then the
body count, then each tube's two bodies as one-based row numbers into the bodies
block. Numbers within a pair are comma separated and every field is semicolon
terminated, so a lone number always opens a section. The example file reads
``8;1,2;2,3;3,4;4,5;4,7;4;3,4;3,2;4,2;``. The one-based convention is stated because a
zero-based implementation would disagree with every file ever written and see them all
as mismatches.

Frames
------

A column's suffix names the frame of its vectors, following KiteUtils.jl, and a
rotation reads ``Q_<from>_to_<to>``:

``_CAD``
   The CAD design frame the geometry was drawn in.

``_ENU``
   The world frame: east, north, up.

``_KA``
   The owning body's kite-aero frame: x from leading to trailing edge, y from the left
   to the right tip, z up.

``pos_CAD`` is **design** geometry. Never draw it as if it were a world position: the
position of a point in the ENU world frame depends on elevation, azimuth, heading and
tether length, which are state, not structure. A body's frame is ``Q_KA_to_CAD`` in a
structure document and ``Q_KA_to_ENU`` in a state log, which is the same rotation
composed with the placement.

The transforms that place CAD geometry into the world are **not part of this schema**,
and not because they are unfinished. Placement is a separate concern from structure:
the same structure flies at any elevation.

What is not described here
--------------------------

Live state: positions, velocities, forces, twist angles, reel-out lengths. A structure
is written once; state is written every step, which is why it belongs in the columns
of a log rather than in this document.

Example
-------

``examples/structure/minimal_structure.yml`` exercises every block: a ground anchor, a
three-segment tether, a control unit on the bridle, and one wing whose left and right
leading-edge tubes are bodies, joined to each other and strutted back to the wing. It
is illustrative rather than a physical system; a worked kite follows once a writer
emits conforming files.
