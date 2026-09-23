"""Sphinx directive rendering the columns each table block of a schema requires."""

import re
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.statemachine import StringList
from ruamel.yaml import YAML
from sphinx.util.nodes import nested_parse_with_titles


def required_columns(block):
    """The required columns of a table block, as (header, unit, description) triples."""
    for part in block.get("allOf", []):
        table = part.get("properties", {})
        if "headers" in table:
            return [(header["const"], unit["const"], header.get("description", "").strip())
                    for header, unit in zip(table["headers"]["items"],
                                            table["units"]["items"])]
    return []


def column_table(name, columns):
    """A list-table of one block's columns, as reStructuredText lines."""
    lines = [f".. list-table:: ``{name}``", "   :header-rows: 1", "   :widths: 2 1 6", "",
             "   * - Column", "     - Unit", "     - Meaning"]
    for header, unit, description in columns:
        literal = re.sub(r"`([^`]+)`", r"``\1``", " ".join(description.split()))
        lines += [f"   * - ``{header}``", f"     - ``{unit}``", f"     - {literal}"]
    return lines + [""]


class SchemaColumns(Directive):
    """`.. schema-columns:: <path>`: one column table per table block, in schema order."""

    required_arguments = 1

    def run(self):
        source = Path(self.state.document.current_source).parent / self.arguments[0]
        schema = YAML(typ="safe").load(source.read_text())
        lines = []
        for name, block in schema["properties"].items():
            columns = required_columns(block)
            if columns:
                lines += column_table(name, columns)
        section = nodes.container()
        nested_parse_with_titles(self.state, StringList(lines, source=str(source)), section)
        return section.children


def setup(app):
    app.add_directive("schema-columns", SchemaColumns)
    return {"parallel_read_safe": True}
