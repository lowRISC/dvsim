# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test flow configuration checking."""

from pathlib import Path

import hjson
from hamcrest import assert_that, equal_to

from dvsim.check.flow import check_flow_config, detect_flow_type


def test_check_valid_lint_config() -> None:
    """Test checking a valid lint flow configuration."""
    fixtures_dir = Path(__file__).parent.parent / "flow" / "fixtures"
    config_file = fixtures_dir / "example_lint.hjson"

    success, message, flow_type = check_flow_config(config_file)

    assert_that(success, equal_to(True))
    assert_that(flow_type, equal_to("lint"))
    assert_that("aes_dv_lint" in message, equal_to(True))


def test_check_invalid_lint_config(tmp_path: Path) -> None:
    """Test checking an invalid lint flow configuration."""
    config_file = tmp_path / "invalid_lint.hjson"
    config_data = {
        "flow": "lint",
        # Missing required 'name' field
    }
    config_file.write_text(hjson.dumps(config_data))

    success, message, flow_type = check_flow_config(config_file)

    assert_that(success, equal_to(False))
    assert_that(flow_type, equal_to("lint"))
    assert_that("Invalid" in message, equal_to(True))


def test_check_missing_flow_field(tmp_path: Path) -> None:
    """Test checking a config without a flow field."""
    config_file = tmp_path / "no_flow.hjson"
    config_data = {"name": "test"}
    config_file.write_text(hjson.dumps(config_data))

    success, message, flow_type = check_flow_config(config_file)

    assert_that(success, equal_to(False))
    assert_that(flow_type, equal_to(None))
    assert_that("No 'flow' field" in message, equal_to(True))


def test_check_nonexistent_file(tmp_path: Path) -> None:
    """Test checking a file that doesn't exist."""
    config_file = tmp_path / "nonexistent.hjson"

    success, message, flow_type = check_flow_config(config_file)

    assert_that(success, equal_to(False))
    assert_that(flow_type, equal_to(None))
    assert_that("not found" in message.lower(), equal_to(True))


def test_check_invalid_hjson(tmp_path: Path) -> None:
    """Test checking a file with invalid hjson syntax."""
    config_file = tmp_path / "invalid.hjson"
    config_file.write_text("{invalid hjson content")

    success, message, flow_type = check_flow_config(config_file)

    assert_that(success, equal_to(False))
    assert_that(flow_type, equal_to(None))
    assert_that("parse" in message.lower(), equal_to(True))


def test_check_unsupported_flow_type(tmp_path: Path) -> None:
    """Test checking a config with an unsupported flow type."""
    config_file = tmp_path / "sim.hjson"
    config_data = {
        "name": "test_sim",
        "flow": "sim",
    }
    config_file.write_text(hjson.dumps(config_data))

    success, message, flow_type = check_flow_config(config_file)

    assert_that(success, equal_to(False))
    assert_that(flow_type, equal_to("sim"))
    assert_that("not yet implemented" in message, equal_to(True))


def test_detect_flow_type() -> None:
    """Test detecting flow type from config file."""
    fixtures_dir = Path(__file__).parent.parent / "flow" / "fixtures"
    config_file = fixtures_dir / "example_lint.hjson"

    flow_type = detect_flow_type(config_file)

    assert_that(flow_type, equal_to("lint"))


def test_detect_flow_type_missing(tmp_path: Path) -> None:
    """Test detecting flow type when field is missing."""
    config_file = tmp_path / "no_flow.hjson"
    config_data = {"name": "test"}
    config_file.write_text(hjson.dumps(config_data))

    flow_type = detect_flow_type(config_file)

    assert_that(flow_type, equal_to(None))
