# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Check flow configuration files for validity."""

from pathlib import Path

import hjson

from dvsim.linting.parser import parse_lint_flow_config


class FlowCheckError(Exception):
    """Error checking flow configuration."""


def detect_flow_type(hjson_path: Path) -> str | None:
    """Detect the flow type from an hjson file.

    Args:
        hjson_path: Path to the hjson configuration file

    Returns:
        Flow type string (e.g., "lint", "sim") or None if not detected

    Raises:
        FlowCheckError: If the file cannot be read or parsed

    """
    try:
        with hjson_path.open() as f:
            data = hjson.load(f, use_decimal=True)
    except hjson.HjsonDecodeError as e:
        msg = f"Failed to parse hjson: {e}"
        raise FlowCheckError(msg) from e
    except OSError as e:
        msg = f"Failed to read file: {e}"
        raise FlowCheckError(msg) from e

    return data.get("flow")


def check_flow_config(hjson_path: Path) -> tuple[bool, str, str | None]:
    """Check a flow configuration file for validity.

    Args:
        hjson_path: Path to the hjson configuration file

    Returns:
        Tuple of (success, message, flow_type):
        - success: True if config is valid, False otherwise
        - message: Human-readable message describing the result
        - flow_type: The detected flow type or None

    """
    hjson_path = Path(hjson_path)

    if not hjson_path.exists():
        return False, f"File not found: {hjson_path}", None

    # Detect flow type
    try:
        flow_type = detect_flow_type(hjson_path)
    except FlowCheckError as e:
        return False, str(e), None

    if flow_type is None:
        return False, "No 'flow' field found in configuration", None

    # Check based on flow type
    if flow_type == "lint":
        try:
            config = parse_lint_flow_config(hjson_path)
        except (FileNotFoundError, RuntimeError) as e:
            return False, f"Invalid lint flow config: {e}", flow_type
        else:
            return True, f"Valid lint flow config: {config.name}", flow_type

    # Other flow types not yet supported
    return False, f"Flow type '{flow_type}' checking not yet implemented", flow_type
