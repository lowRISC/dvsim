# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""An abstraction for maintaining job runtime and its units."""

__all__ = ("JobTime",)

# Supported time units and the divisor required to convert the value in the
# current unit to the next largest unit.
TIME_UNITS = ["h", "m", "s", "ms", "us", "ns", "ps", "fs"]
TIME_DIVIDERS = [60.0] * 3 + [1000.0] * 5


# TODO: Migrate to Time instead of a custom implementation
class JobTime:  # noqa: PLW1641 # Muitable object should not implement __hash__
    """Job runtime."""

    def __init__(self, time: float = 0.0, unit: str = "s", *, normalize: bool = True) -> None:
        """Initialise."""
        self._time: float = time
        self._unit: str = unit

        self.set(
            time=time,
            unit=unit,
            normalize=normalize,
        )

    @property
    def time(self) -> float:
        """Get time."""
        return self._time

    @property
    def unit(self) -> str:
        """Get unit."""
        return self._unit

    @staticmethod
    def _check_valid_unit(unit: str) -> None:
        """Assert unit is valid."""
        if unit not in TIME_UNITS:
            msg = f"unit '{unit}' is not a supported time unit: {TIME_UNITS}"
            raise KeyError(msg)

    def set(self, time: float, unit: str, *, normalize: bool = True) -> None:
        """Public API to set the instance variables time, unit."""
        self._check_valid_unit(unit=unit)

        self._time = time
        self._unit = unit

        if normalize:
            self._normalize()

    def get(self) -> tuple[float, str]:
        """Return the time and unit as a tuple."""
        return self._time, self._unit

    def with_unit(self, unit: str) -> "JobTime":
        """Return a copy with the given unit.

        Note that the scaling may not be lossless due to rounding errors and
        limited precision.
        """
        self._check_valid_unit(unit=unit)

        target_index = TIME_UNITS.index(unit)
        index = TIME_UNITS.index(self._unit)

        new_time = self._time
        while index < target_index:
            index += 1
            new_time *= TIME_DIVIDERS[index]

        while index > target_index:
            new_time /= TIME_DIVIDERS[index]
            index -= 1

        return JobTime(
            time=new_time,
            unit=unit,
            normalize=False,
        )

    def _normalize(self) -> None:
        """Brings the time and its units to a more meaningful magnitude.

        If the time is very large with a lower magnitude, this method divides
        the time to get it to the next higher magnitude recursively, stopping
        if the next division causes the time to go < 1. Examples:
          123123232ps -> 123.12us
          23434s -> 6.509h

        The supported magnitudes and their associated divider values are
        provided by TIME_UNITS and TIME_DIVIDERS.
        """
        if self._time == 0:
            return

        index = TIME_UNITS.index(self._unit)
        normalized_time = self._time

        while index > 0 and normalized_time >= TIME_DIVIDERS[index]:
            normalized_time = normalized_time / TIME_DIVIDERS[index]
            index = index - 1

        self._time = normalized_time
        self._unit = TIME_UNITS[index]

    def _with_common_units(self, other: "JobTime") -> tuple[float, float]:
        """Convert times to common units for relative comparison.

        Returns:
            tuple of both times as floats in the smallest unit to be
        used for comparison.

        """
        stime = self._time
        otime = other.time

        sidx = TIME_UNITS.index(self._unit)
        oidx = TIME_UNITS.index(other.unit)

        # If the time units are not the same
        if sidx != oidx:
            # Pick the smallest unit and standardise on that unit. This means
            # the comparison is less likely to be lossy.
            if sidx < oidx:
                stime = self.with_unit(other.unit).time
            else:
                otime = other.with_unit(self.unit).time

        return stime, otime

    def __str__(self) -> str:
        """Time as a string <time><unit>.

        The time value is truncated to 3 decimal places.
        Returns an empty string if the __time is set to 0.
        """
        if self._time == 0:
            return ""
        return f"{self._time:.3f}{self._unit}"

    def __eq__(self, other: object) -> bool:
        """Check equality."""
        if not isinstance(other, JobTime):
            return False

        stime, otime = self._with_common_units(other=other)

        return stime == otime

    def __gt__(self, other: object) -> bool:
        """Check time is greater than."""
        if not isinstance(other, JobTime):
            msg = f"Can't compare {self} with {other}"
            raise TypeError(msg)

        stime, otime = self._with_common_units(other=other)

        return stime > otime

    def __ge__(self, other: object) -> bool:
        """Check time is greater than or equal to."""
        if not isinstance(other, JobTime):
            msg = f"Can't compare {self} with {other}"
            raise TypeError(msg)

        stime, otime = self._with_common_units(other=other)

        return stime >= otime
