AWE System Structure Schema
===========================

The structure schema describes the **resolved structural topology** of an AWE system:
the points, and the segments, tethers, winches, pulleys and wing sections that connect
them. It is the layer :doc:`system_schema` leaves free-form — its ``wing_sections``,
``bridle_nodes``, ``bridle_lines`` and ``bridle_connections`` blocks are bare
``type: object`` under ``additionalProperties: true``, so today any content validates.

Plotting is the clearest symptom of not having it. Two tools cannot draw each other's
system because neither can describe it, so every viewer is written against one model.
With a shared structure, drawing a state is one code path and every model gets every
viewer.

.. note::
   All quantities follow the SI unit convention used throughout awesIO.

Canonical form only
-------------------

A conforming file is **fully resolved and expanded**: no variable substitution block,
no segment counts left to expand, every point and segment explicit. It is readable
with nothing beyond a YAML or JSON parser.

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
     headers: [name, point_a, point_b]
     data:
       - [seg_1, ground, tether_1]
       - [seg_2, tether_1, tether_2]

A block may carry columns beyond the ones the schema requires. **A reader addresses
columns by header, never by position** — that is what lets a later minor version
append a column without breaking an older reader.

YAML and JSON are two encodings of one model. JSON is the machine encoding, and it
travels in the table-level metadata of an Arrow state log under the key ``topology``,
which is what makes a log self-describing: plotting it needs no sidecar file.

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
is ASCII and built in document order: the point count, a semicolon, then each
segment's two endpoints as **one-based** row numbers into the points block, comma
separated and semicolon terminated. The example file reads ``6;1,2;2,3;3,4;4,5;4,6;``.
The one-based convention is stated because a zero-based implementation would disagree
with every file ever written and see them all as mismatches.

CAD geometry is not a world position
------------------------------------

``pos_cad`` is **design** geometry. Never draw it as if it were a world position: the
world position of a point depends on elevation, azimuth, heading and tether length,
which are state, not structure.

The ``transforms`` block that maps CAD geometry into the world frame is **deliberately
absent from version 0.1**. It is the one part of the document whose meaning depends on
a settled frame convention, and that convention is still being unified upstream. Until
"the orientation in this file" means exactly one thing, specifying it here would bake
in the ambiguity. It arrives as an additive minor version once the frames settle.

Scope of version 0.1
--------------------

Version 0.1 specifies **connectivity and design geometry**: which points exist, where
they sit in the CAD frame, what connects to what, and how segments group into tethers,
winches, pulleys and wing sections. That much is settled — it is what existing
writers already emit and existing viewers already read.

Deliberately not yet specified:

* **Material and section properties** — rest length, diameter, density.
* **Constitutive models** — linear versus tabulated springs, elastic versus
  Timoshenko joints, and the type-dependent validation that goes with them.
* **Transforms**, for the frame reason above.
* A **wings** block. ``wing_idx`` on a point is consequently the one reference in the
  document that is not by name, and points into nothing. It is marked provisional in
  the schema.

These are not oversights and they are not hard to add: each is a column or a block
appended under the forward-compatibility rule above. They are held back because a
schema for a constitutive model is that model's type hierarchy written down, and
writing it before the model exists would mean guessing, then breaking the guess. The
reference implementation is being factored out now; these blocks follow it rather than
lead it.

Example
-------

``examples/structure/minimal_structure.yml`` is the smallest file that exercises every
block. A worked, physically meaningful system follows once a writer emits conforming
files.
