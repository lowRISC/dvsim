# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test lint flow configuration parser."""

from pathlib import Path

import hjson
import pytest
from hamcrest import assert_that, calling, equal_to, has_length, raises
from pydantic import ValidationError

from dvsim.linting.config import LintFlowConfig, MessageBucket
from dvsim.linting.parser import load_lint_config_from_dict, parse_lint_flow_config


def test_parse_minimal_lint_config(tmp_path: Path) -> None:
    """Test parsing a minimal lint configuration."""
    config_data = {
        "name": "test_lint",
        "flow": "lint",
    }

    config_file = tmp_path / "test_lint.hjson"
    config_file.write_text(hjson.dumps(config_data))

    config = parse_lint_flow_config(config_file)

    assert_that(config.name, equal_to("test_lint"))
    assert_that(config.flow, equal_to("lint"))
    assert_that(config.is_style_lint, equal_to(False))
    assert_that(config.report_severities, equal_to(["info", "warning", "error"]))
    assert_that(config.fail_severities, equal_to(["warning", "error"]))


def test_parse_full_lint_config(tmp_path: Path) -> None:
    """Test parsing a full lint configuration with all fields."""
    config_data = {
        "name": "aes_lint",
        "flow": "lint",
        "dut": "aes",
        "fusesoc_core": "lowrisc:dv:aes_sim",
        "additional_fusesoc_argument": "--mapping=lowrisc:systems:top_earlgrey:0.1",
        "build_dir": "{scratch_path}/{build_mode}",
        "build_log": "{build_dir}/{tool}.log",
        "build_cmd": "fusesoc",
        "build_opts": ["--cores-root {proj_root}/hw", "run"],
        "is_style_lint": False,
        "report_severities": ["info", "warning", "error"],
        "fail_severities": ["warning", "error"],
        "message_buckets": [
            {"category": "flow", "severity": "info", "label": ""},
            {"category": "flow", "severity": "warning", "label": ""},
            {"category": "flow", "severity": "error", "label": ""},
            {"category": "lint", "severity": "info", "label": ""},
            {"category": "lint", "severity": "warning", "label": ""},
            {"category": "lint", "severity": "error", "label": ""},
        ],
    }

    config_file = tmp_path / "aes_lint.hjson"
    config_file.write_text(hjson.dumps(config_data))

    config = parse_lint_flow_config(config_file)

    assert_that(config.name, equal_to("aes_lint"))
    assert_that(config.dut, equal_to("aes"))
    assert_that(config.fusesoc_core, equal_to("lowrisc:dv:aes_sim"))
    assert_that(config.build_opts, has_length(2))
    assert_that(config.message_buckets, has_length(6))
    assert_that(config.message_buckets[0].category, equal_to("flow"))
    assert_that(config.message_buckets[0].severity, equal_to("info"))


def test_parse_style_lint_config(tmp_path: Path) -> None:
    """Test parsing a style lint configuration."""
    config_data = {
        "name": "verible_style_lint",
        "flow": "lint",
        "is_style_lint": True,
        "tool": "veriblelint",
    }

    config_file = tmp_path / "style_lint.hjson"
    config_file.write_text(hjson.dumps(config_data))

    config = parse_lint_flow_config(config_file)

    assert_that(config.name, equal_to("verible_style_lint"))
    assert_that(config.is_style_lint, equal_to(True))
    assert_that(config.tool, equal_to("veriblelint"))


def test_load_lint_config_from_dict() -> None:
    """Test loading configuration from a dictionary."""
    config_dict = {
        "name": "dict_test",
        "flow": "lint",
        "message_buckets": [
            {"category": "lint", "severity": "error", "label": "Errors"},
        ],
    }

    config = load_lint_config_from_dict(config_dict)

    assert_that(config.name, equal_to("dict_test"))
    assert_that(config.message_buckets, has_length(1))
    assert_that(config.message_buckets[0].category, equal_to("lint"))


def test_message_bucket_model() -> None:
    """Test the MessageBucket pydantic model."""
    bucket = MessageBucket(category="flow", severity="warning", label="Flow Warnings")

    assert_that(bucket.category, equal_to("flow"))
    assert_that(bucket.severity, equal_to("warning"))
    assert_that(bucket.label, equal_to("Flow Warnings"))


def test_message_bucket_default_label() -> None:
    """Test MessageBucket with default label."""
    bucket = MessageBucket(category="lint", severity="info")

    assert_that(bucket.category, equal_to("lint"))
    assert_that(bucket.severity, equal_to("info"))
    assert_that(bucket.label, equal_to(""))


def test_parse_missing_file_raises() -> None:
    """Test that parsing a non-existent file raises FileNotFoundError."""
    assert_that(
        calling(parse_lint_flow_config).with_args("/nonexistent/file.hjson"),
        raises(FileNotFoundError),
    )


def test_parse_invalid_hjson_raises(tmp_path: Path) -> None:
    """Test that parsing invalid hjson raises RuntimeError."""
    config_file = tmp_path / "invalid.hjson"
    config_file.write_text("{invalid hjson content")

    # Should raise RuntimeError for invalid hjson syntax
    with pytest.raises(RuntimeError) as exc_info:
        parse_lint_flow_config(config_file)

    # Verify the error message mentions the file and parsing failure
    assert str(config_file) in str(exc_info.value)
    assert "parse" in str(exc_info.value).lower()


def test_missing_required_field_raises() -> None:
    """Test that missing required fields raise ValidationError."""
    config_dict = {
        "flow": "lint",
        # Missing required 'name' field
    }

    # ValidationError should be raised directly by Pydantic
    with pytest.raises(ValidationError) as exc_info:
        load_lint_config_from_dict(config_dict)

    # Verify the error mentions the missing 'name' field
    assert "name" in str(exc_info.value)


def test_extra_fields_forbidden() -> None:
    """Test that extra fields are forbidden in the configuration."""
    config_dict = {
        "name": "test",
        "flow": "lint",
        "custom_field": "custom_value",
    }

    # Should raise ValidationError for unknown fields
    with pytest.raises(ValidationError) as exc_info:
        load_lint_config_from_dict(config_dict)

    # Verify the error mentions the unexpected field
    assert "custom_field" in str(exc_info.value)


def test_integration_with_example_hjson() -> None:
    """Integration test with a realistic lint flow hjson file."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    config_file = fixtures_dir / "example_lint.hjson"

    config = parse_lint_flow_config(config_file)

    # Build expected config
    expected = LintFlowConfig(
        name="aes_dv_lint",
        flow="lint",
        dut="aes",
        fusesoc_core="lowrisc:dv:aes_sim",
        additional_fusesoc_argument="--mapping=lowrisc:systems:top_earlgrey:0.1",
        build_dir="{scratch_path}/{build_mode}",
        build_log="{build_dir}/{tool}.log",
        build_cmd="fusesoc",
        build_opts=[
            "--cores-root {proj_root}/hw",
            "run",
            "--target={flow}",
            "--tool={tool}",
            "--work-root={build_dir}/fusesoc-work",
        ],
        is_style_lint=False,
        report_severities=["info", "warning", "error"],
        fail_severities=["warning", "error"],
        message_buckets=[
            MessageBucket(category="flow", severity="info", label="Flow Info"),
            MessageBucket(category="flow", severity="warning", label="Flow Warnings"),
            MessageBucket(category="flow", severity="error", label="Flow Errors"),
            MessageBucket(category="lint", severity="info", label="Lint Info"),
            MessageBucket(category="lint", severity="warning", label="Lint Warnings"),
            MessageBucket(category="lint", severity="error", label="Lint Errors"),
        ],
        tool="ascentlint",
        scratch_path="/tmp/dvsim/scratch",  # noqa: S108
        rel_path="hw/ip/aes/dv/lint/{tool}",
    )

    assert_that(config.model_dump(), equal_to(expected.model_dump()))
