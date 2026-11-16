# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Report data models."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict

__all__ = (
    "CfgExtensionMeta",
    "GitRevisionMeta",
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
    commit_short: str
    """Shortened Git commit sha of the IP the tests are run against."""
    dirty: bool = False
    """Whether the working tree had uncommitted changes at run time."""
    branch: str
    """Git branch"""
    url: str | None
    """URL to where the IP can be found in git (e.g. github). None if the local
    checkout has no ``origin`` remote (typical for developer clones)."""
    revision_info: str | None
    """Optional revision info string to use for custom info instead of the above fields."""

    def variant_name(self, sep: str = "_") -> str:
        """Name suffixed with the variant for disambiguation."""
        return f"{self.name}{sep}{self.variant}" if self.variant else self.name


class ToolMeta(BaseModel):
    """Meta data for an EDA tool."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    """Name of the tool."""
    version: str
    """Version of the tool."""


class CfgExtensionMeta(BaseModel):
    """A cfg extension (--cfg-extend) merged into a flow's cfg."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    """Path of the extension file."""
    revision: "GitRevisionMeta | None" = None
    """The git revision of the checkout that holds the extension file (not of
    any files it imports from elsewhere), or None if it isn't in git."""

    @property
    def name(self) -> str:
        """The name of the extension file."""
        return Path(self.path).name


class GitRevisionMeta(BaseModel):
    """The git revision of a checkout, when the run started."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    origin: str | None
    """URL of the ``origin`` remote (credentials stripped), or None."""
    commit: str
    """Git commit."""
    commit_short: str
    """Shortened git commit."""
    dirty: bool
    """Whether the checkout had uncommitted changes, or didn't track the file."""
