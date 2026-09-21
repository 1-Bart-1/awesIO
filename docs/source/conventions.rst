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

A vector's name ends in a suffix naming its frame, following KiteUtils.jl:

``_cad``
   The CAD design frame the geometry was drawn in.

``_KA``
   The owning body's kite-aero frame: x from leading to trailing edge, y from the left
   to the right tip, z up.
