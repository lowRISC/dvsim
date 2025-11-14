# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Render template."""

from collections.abc import Mapping
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

__all__ = ("render_template",)

_env: Environment | None = None


def render_template(path: Path, data: Mapping[str, object] | None = None) -> str:
    """Render a template from the relative path.

    Args:
        path: relative path to the template
        data: mapping of key/value pairs to send to the template renderer

    Returns:
        string containing the rendered template

    """
    global _env

    if _env is None:
        _env = Environment(
            loader=PackageLoader("dvsim"),
            autoescape=select_autoescape(),
        )

    template = _env.get_template("mytemplate.html")

    return template.render(data)
