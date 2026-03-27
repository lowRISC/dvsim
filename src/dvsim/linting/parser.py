# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Parser for lint flow hjson configuration files."""

from pathlib import Path

import hjson
from pydantic import ValidationError

from dvsim.linting.config import LintFlowConfig, MessageBucket


def parse_lint_flow_config(hjson_path: str | Path) -> LintFlowConfig:
    """Parse a lint flow hjson configuration file.

    This function loads an hjson file and validates it against the LintFlowConfig
    pydantic model. This is a new parser specifically for lint flows and does not
    modify the existing flow config parsing infrastructure.

    Args:
        hjson_path: Path to the hjson configuration file

    Returns:
        LintFlowConfig: Validated lint flow configuration

    Raises:
        FileNotFoundError: If the hjson file doesn't exist
        ValidationError: If the hjson data doesn't match the expected schema
        RuntimeError: If there are other errors parsing the hjson

    Example:
        >>> config = parse_lint_flow_config("path/to/lint_cfg.hjson")
        >>> print(config.name)
        >>> print(config.report_severities)

    """
    hjson_path = Path(hjson_path)

    if not hjson_path.exists():
        msg = f"Configuration file not found: {hjson_path}"
        raise FileNotFoundError(msg)

    # Parse the hjson file using hjson library directly
    try:
        with hjson_path.open() as f:
            hjson_data = hjson.load(f, use_decimal=True)
    except hjson.HjsonDecodeError as e:
        msg = f"Failed to parse hjson file {hjson_path}: {e}"
        raise RuntimeError(msg) from e
    except OSError as e:
        msg = f"Failed to read hjson file {hjson_path}: {e}"
        raise RuntimeError(msg) from e

    # Validate against the pydantic model
    try:
        # Convert message_buckets from list of dicts to list of MessageBucket objects
        if "message_buckets" in hjson_data:
            hjson_data["message_buckets"] = [
                MessageBucket(**bucket) if isinstance(bucket, dict) else bucket
                for bucket in hjson_data["message_buckets"]
            ]

        return LintFlowConfig(**hjson_data)
    except ValidationError as e:
        msg = f"Configuration validation failed for {hjson_path}:\n{e}"
        raise RuntimeError(msg) from e


def load_lint_config_from_dict(config_dict: dict) -> LintFlowConfig:
    """Load a lint flow configuration from a dictionary.

    This is useful for loading inline configurations or for testing.

    Args:
        config_dict: Dictionary containing lint flow configuration

    Returns:
        LintFlowConfig: Validated lint flow configuration

    Raises:
        ValidationError: If the dictionary doesn't match the expected schema

    Example:
        >>> config_dict = {"name": "test_lint", "flow": "lint"}
        >>> config = load_lint_config_from_dict(config_dict)

    """
    # Convert message_buckets if present
    if "message_buckets" in config_dict:
        config_dict["message_buckets"] = [
            MessageBucket(**bucket) if isinstance(bucket, dict) else bucket
            for bucket in config_dict["message_buckets"]
        ]

    return LintFlowConfig(**config_dict)
