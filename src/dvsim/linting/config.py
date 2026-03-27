# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Pydantic models for lint flow configuration."""

from pydantic import BaseModel, ConfigDict, Field


class MessageBucket(BaseModel):
    """Message bucket configuration for categorizing lint messages."""

    model_config = ConfigDict(frozen=True)

    category: str = Field(..., description="Message category (e.g., 'flow', 'lint')")
    severity: str = Field(..., description="Message severity (e.g., 'info', 'warning', 'error')")
    label: str = Field(default="", description="Optional label for the bucket")


class LintFlowConfig(BaseModel):
    """Configuration for the lint flow.

    This model represents the core lint flow configuration that can be parsed
    from hjson files. It focuses on lint-specific fields and does not include
    all the base flow configuration fields that are handled by the existing
    FlowCfg class hierarchy.
    """

    # Flow identification
    flow: str = Field(default="lint", description="Flow type identifier")
    name: str = Field(..., description="Name of the lint configuration")

    # Build configuration
    build_dir: str = Field(default="", description="Build directory path")
    build_log: str = Field(default="", description="Build log file path")
    build_cmd: str = Field(default="", description="Build command")
    build_opts: list[str] = Field(default_factory=list, description="Build options")

    # FuseSoC configuration
    fusesoc_core: str = Field(default="", description="FuseSoC core to use")
    additional_fusesoc_argument: str = Field(
        default="", description="Additional FuseSoC argument (e.g., mapping)"
    )

    # Lint-specific configuration
    is_style_lint: bool = Field(default=False, description="Whether this is a style lint run")
    report_severities: list[str] = Field(
        default_factory=lambda: ["info", "warning", "error"],
        description="Message severities to include in reports",
    )
    fail_severities: list[str] = Field(
        default_factory=lambda: ["warning", "error"],
        description="Message severities that cause the flow to fail",
    )
    message_buckets: list[MessageBucket] = Field(
        default_factory=list, description="Message bucket configuration"
    )

    # Tool configuration
    tool: str | None = Field(default=None, description="Lint tool to use")
    dut: str = Field(default="", description="Design under test name")

    # Directory paths
    scratch_path: str = Field(default="", description="Scratch directory path")
    rel_path: str = Field(default="", description="Relative path for results")

    # Import and use configurations
    import_cfgs: list[str] = Field(
        default_factory=list, description="Configuration files to import"
    )
    use_cfgs: list[dict | str] = Field(
        default_factory=list, description="Sub-configurations to use (for primary configs)"
    )

    model_config = ConfigDict(
        frozen=True,  # Make the model immutable
        extra="forbid",  # Forbid extra fields to catch configuration errors
    )
