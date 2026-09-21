Conventions
===========

These rules hold for every awesIO file, whichever schema it follows. A schema page
states only what is specific to its own file.

Which schema a file follows
---------------------------

Every file opens with a ``metadata`` block. Its ``schema`` field is pinned to the
schema's filename, such as ``structure_schema.yml``, and names *which* schema the
file follows, never which version. ``awesio.validator.validate`` reads it to pick the schema, so a file is validated without being told its type:

.. code-block:: python

   from awesio.validator import validate

   data = validate("your_file.yml")

Units
-----

All quantities are in **SI units**.

Versioning
----------

``metadata.awesIO_version`` is the version the file was written against. **A reader
refuses an unknown major version and warns on an unknown minor one**, so a breaking
change is caught at load rather than silently misread. A minor version only adds.

Names a reader does not know
----------------------------

A tool may carry data of its own as extra top-level blocks of any shape. ``metadata``
and the blocks a schema defines keep the keys that schema lists, except where the
schema opens one itself. **A reader ignores every name it does not know**, so a file
written for one tool still loads in another.

A later minor version may claim any such name for the schema, after which the tool
renames its own.

Frames
------

A vector's name ends in a suffix naming the frame it is written in. Every frame is
right-handed and in metres. The frames are those of `KiteUtils.jl
<https://opensourceawe.github.io/KiteUtils.jl/dev/reference_frames/>`_.

``_KA``
   A body's own frame: x from the leading to the trailing edge, y from the left to the
   right tip, z up.

``_CAD``
   The design frame the geometry is drawn in, with the axes of the kite's KA at zero
   rotation.
   Its origin is the point a structure file's ``metadata.cad_origin`` names, whose
   ``pos_CAD`` is ``[0, 0, 0]``: for a soft kite, the KCU.

``_ENU``
   The world: x east, y north, z up, with its origin at the tether exit point of the
   ground station.

A rotation reads ``Q_<from>_to_<to>``: a unit quaternion ``q``, scalar first
``[w, x, y, z]``, that takes a vector's components in ``<from>`` to the same vector's
components in ``<to>``, ``v_to = q v_from q*``. Its rotation matrix has ``<from>``'s
axes, written in ``<to>``, as its columns.
