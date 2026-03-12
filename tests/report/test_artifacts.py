# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test report artifacts."""

from pathlib import Path

from hamcrest import assert_that, empty, equal_to, is_not

from dvsim.report.artifacts import render_static_content

__all__ = ()


class TestRenderStaticContent:
    """Test render_static_content."""

    @staticmethod
    def test_artifacts() -> None:
        """Test that static files are able to be rendered."""
        artifacts = render_static_content(
            static_files=["css/style.css"],
        )

        assert_that(set(artifacts.keys()), equal_to({"css/style.css"}))
        assert_that(artifacts["css/style.css"], is_not(empty()))

    @staticmethod
    def test_render_to_file(tmp_path: Path) -> None:
        """Test that static files are saved to outdir."""
        artifacts = render_static_content(
            static_files=["css/style.css"],
            outdir=tmp_path,
        )

        output_file = tmp_path / "css/style.css"
        assert_that(output_file.exists(), equal_to(True))
        assert_that(
            output_file.read_text(),
            equal_to(artifacts["css/style.css"]),
        )
