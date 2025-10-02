# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test report index generation."""

from pathlib import Path

import pytest
from hamcrest import assert_that, contains_string

from dvsim.report.index import create_html_redirect_file, gen_top_level_index

__all__ = ()


def test_create_html_redirect_file(tmp_path: Path) -> None:
    """Test that a file is create and contains the target url.

    This is a limited smoke test doesn't check the redirect functionality itself
    that needs to be a manual test.
    """
    redirect_file = tmp_path / "redirect.html"

    create_html_redirect_file(path=redirect_file, target_url="somewhere")

    assert_that(redirect_file.read_text(), contains_string("somewhere"))


@pytest.mark.parametrize("dirs", [{"dvsim_run_class_a", "dvsim_run_class_b"}])
def test_gen_top_level_index(tmp_path: Path, dirs: set[str]) -> None:
    """Test that a top level index is generated."""
    index_file = tmp_path / "index.html"
    for d in dirs:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    gen_top_level_index(base_path=tmp_path, extra_env={})

    index = index_file.read_text()
    for d in dirs:
        assert_that(index, contains_string(d))
