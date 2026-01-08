# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Report data models."""

from pydantic import BaseModel, ConfigDict

__all__ = (
    "IPMeta",
    "ToolMeta",
)


class IPMeta(BaseModel):
    """Meta data for an IP block."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    """Name of the IP."""
    variant: str | None = None
    """Variant of the IP if there is one."""

    commit: str
    """Git commit sha of the IP the tests are run against."""
    branch: str
    """Git branch"""
    url: str
    """URL to where the IP can be found in git (e.g. github)."""


class ToolMeta(BaseModel):
    """Meta data for an EDA tool."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    """Name of the tool."""
    version: str
    """Version of the tool."""
