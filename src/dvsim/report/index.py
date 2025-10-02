# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Report indexing."""

from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory

from logzero import logger

from dvsim.templates.render import render_template
from dvsim.utils.rclone import rclone_copy, rclone_list_dirs

__all__ = ("create_html_redirect_file",)


def create_html_redirect_file(*, path: Path, target_url: str) -> None:
    """Create a HTML redirect file to the given URL."""
    output = render_template(
        path=Path("reports") / "redirect.html",
        data={"url": target_url},
    )

    if output:
        path.write_text(output)


def gen_top_level_index(
    *,
    base_path: Path | str,
    extra_env: Mapping | None = None,
) -> None:
    """Generate a top level index.

    Args:
        base_path: path to the reporting base directory, either a Path object or
            a string that rclone understands.
        extra_env: mapping of environment variable key/value pairs for rclone

    """
    logger.debug("Generating top level index for '%s'", str(base_path))
    dirs = rclone_list_dirs(path=base_path, extra_env=extra_env)

    logger.debug(
        "Found report groups:\n - %s",
        "\n - ".join(dirs),
    )

    output = render_template(
        path=Path("reports") / "index.html",
        data={
            "dirs": dirs,
            "title": "Reports",
            "breadcrumbs": ["Home"],
        },
    )
    if output is None:
        logger.error("index template rendered nothing")
        return

    # The base path could be a remote bucket path, so generate the index locally
    # and then copy it over with rclone.
    with TemporaryDirectory() as tmp_dir:
        base = Path(tmp_dir)

        logger.debug("Generating reports in tmp dir: '%s'", base)

        (base / "index.html").write_text(output)

        for d in dirs:
            report_class_dir = base / d
            report_class_dir.mkdir()

            logger.debug(
                "Generating report group index for '%s'",
                str(d),
            )

            report_dirs = rclone_list_dirs(
                path=f"{base_path}/{d}",
                extra_env=extra_env,
            )

            logger.debug(
                "Found reports:\n - %s",
                "\n - ".join(report_dirs),
            )

            sub_index = render_template(
                path=Path("reports") / "index.html",
                data={
                    "dirs": report_dirs,
                    "title": d,
                    "breadcrumbs": [("../", "Home"), d],
                },
            )
            if sub_index is None:
                logger.error("index template rendered nothing")
                return

            (report_class_dir / "index.html").write_text(sub_index)

        logger.debug("Publishing index changes from temp dir '%s' -> '%s'", base, base_path)

        rclone_copy(
            src_path=base,
            dest_path=base_path,
            extra_env=extra_env,
        )
