# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test template renderer."""

import pytest
from hamcrest import assert_that, empty, is_not

from dvsim.templates.render import render_static


@pytest.mark.parametrize(
    "static_content_path",
    [
        "css/style.css",
        "css/bootstrap.min.css",
        "js/bootstrap.bundle.min.js",
        "js/htmx.min.js",
    ],
)
def test_render_static(static_content_path: str) -> None:
    """Test that static files are able to be rendered."""
    text = render_static(path=static_content_path)

    assert_that(text, is_not(empty()))
