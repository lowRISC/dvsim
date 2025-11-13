# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Render templates for use with report generation.

This directory is also the parent directory containing templates for use with
DVSim. Templates can be referenced relative to this directory.
"""

from collections.abc import Mapping

from jinja2 import Environment, PackageLoader, select_autoescape

__all__ = ("render_template",)

_env: Environment | None = None


def render_template(path: str, data: Mapping[str, object] | None = None) -> str:
    """Render a template packaged with DVSim.

    Args:
        path: relative path to the DVSim template directory
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

    template = _env.get_template(path)

    return template.render(data)
