# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Render template."""

from collections.abc import Mapping
from pathlib import Path

from logzero import logger
from mako import exceptions
from mako.template import Template


def render_template(path: Path, data: Mapping[str, object] | None = None) -> str:
    """Render a template from the relative path.

    Args:
        path: relative path to the template
        data: mapping of key/value pairs to send to the template renderer

    Returns:
        string containing the rendered template

    """
    template_base_path = Path(__file__).parent
    template_path = template_base_path / path

    if not template_path.exists():
        logger.error("Template file not found: %s", template_path)
        raise FileNotFoundError

    try:
        output = Template(filename=str(template_path)).render(**data or {})  # noqa: S702

    except:
        # The NameError exception doesn't contain a useful error message. this
        # has to ge requested seporatly from Mako for some reason?
        logger.error(exceptions.text_error_template().render())
        raise

    if isinstance(output, bytes):
        output = output.decode(encoding="utf8")

    return output
