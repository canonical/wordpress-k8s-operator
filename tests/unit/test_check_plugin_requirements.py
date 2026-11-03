# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the rock build check of bundled plugin WordPress requirements."""

import subprocess  # nosec B404
import typing
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "wordpress_rock" / "check_plugin_requirements.sh"


def make_plugin(
    plugins_dir: Path,
    slug: str,
    header: typing.Optional[str] = None,
    readme: typing.Optional[str] = None,
) -> None:
    """Create a fake plugin directory.

    Args:
        plugins_dir: directory that holds the plugins.
        slug: plugin directory name.
        header: "Requires at least" value in the main plugin file header, if any.
        readme: "Requires at least" value in readme.txt, if any.
    """
    plugin = plugins_dir / slug
    plugin.mkdir()
    lines = ["<?php", "/**", f" * Plugin Name: {slug}"]
    if header is not None:
        lines.append(f" * Requires at least: {header}")
    lines.append(" */")
    (plugin / f"{slug}.php").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if readme is not None:
        (plugin / "readme.txt").write_text(
            f"=== {slug} ===\nRequires at least: {readme}\n", encoding="utf-8"
        )


def run_check(wp_version: str, plugins_dir: Path) -> subprocess.CompletedProcess:
    """Run the check script.

    Args:
        wp_version: WordPress version of the image.
        plugins_dir: directory that holds the plugins.

    Returns:
        The completed process.
    """
    return subprocess.run(  # nosec B603 B607
        ["bash", str(SCRIPT), wp_version, str(plugins_dir)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_compatible_plugins_pass(tmp_path: Path):
    """
    arrange: plugins that need WordPress 6.8 and 5.0.
    act: run the check for WordPress 6.8.1.
    assert: the check passes.
    """
    make_plugin(tmp_path, "a", header="6.8")
    make_plugin(tmp_path, "b", readme="5.0")

    assert run_check("6.8.1", tmp_path).returncode == 0


def test_newer_requirement_fails(tmp_path: Path):
    """
    arrange: a plugin that needs WordPress 7.0.
    act: run the check for WordPress 6.8.1.
    assert: the check fails and names the plugin and both versions.
    """
    make_plugin(tmp_path, "wordpress-seo", header="7.0")

    result = run_check("6.8.1", tmp_path)

    assert result.returncode == 1
    assert "wordpress-seo requires WordPress 7.0, image has 6.8.1" in result.stderr


def test_readme_requirement_is_ignored(tmp_path: Path):
    """
    arrange: a plugin whose readme.txt says 6.9 and whose header has no requirement.
    act: run the check for WordPress 6.8.1.
    assert: the check passes, since WordPress only enforces the plugin header.
    """
    make_plugin(tmp_path, "safe-svg", readme="6.9")

    assert run_check("6.8.1", tmp_path).returncode == 0


def test_header_requirement_used_over_readme(tmp_path: Path):
    """
    arrange: a plugin whose header says 7.0 and whose readme.txt says 6.0.
    act: run the check for WordPress 6.8.1.
    assert: the check fails using the header value.
    """
    make_plugin(tmp_path, "a", header="7.0", readme="6.0")

    result = run_check("6.8.1", tmp_path)

    assert result.returncode == 1
    assert "a requires WordPress 7.0, image has 6.8.1" in result.stderr


def test_directory_without_plugin_files_passes(tmp_path: Path):
    """
    arrange: a directory with no PHP file and no readme, like files/ in the rock source.
    act: run the check for WordPress 6.8.1.
    assert: the check passes.
    """
    (tmp_path / "files").mkdir()

    assert run_check("6.8.1", tmp_path).returncode == 0


def test_plugin_without_requirement_passes(tmp_path: Path):
    """
    arrange: a plugin with no "Requires at least" anywhere.
    act: run the check for WordPress 6.8.1.
    assert: the check passes.
    """
    make_plugin(tmp_path, "wp-markdown")

    assert run_check("6.8.1", tmp_path).returncode == 0


def test_version_compare_is_numeric(tmp_path: Path):
    """
    arrange: a plugin that needs WordPress 6.10.
    act: run the check for WordPress 6.9.
    assert: the check fails, since 6.10 is newer than 6.9.
    """
    make_plugin(tmp_path, "a", header="6.10")

    assert run_check("6.9", tmp_path).returncode == 1


def test_three_part_requirement_equal_to_wp_passes(tmp_path: Path):
    """
    arrange: plugins that need WordPress 6.8.1 and 5.0.0.
    act: run the check for WordPress 6.8.1.
    assert: the check passes.
    """
    make_plugin(tmp_path, "a", header="6.8.1")
    make_plugin(tmp_path, "b", header="5.0.0")

    assert run_check("6.8.1", tmp_path).returncode == 0


def test_crlf_requirement_is_parsed(tmp_path: Path):
    """
    arrange: a plugin header with Windows line endings that needs WordPress 7.0.
    act: run the check for WordPress 6.8.1.
    assert: the check fails and prints the version without the carriage return.
    """
    make_plugin(tmp_path, "a", header="7.0\r")

    result = run_check("6.8.1", tmp_path)

    assert result.returncode == 1
    assert "a requires WordPress 7.0, image has 6.8.1" in result.stderr


def test_all_failures_reported(tmp_path: Path):
    """
    arrange: two plugins that need WordPress 7.0 and 6.9.
    act: run the check for WordPress 6.8.1.
    assert: the check fails and names both plugins.
    """
    make_plugin(tmp_path, "a", header="7.0")
    make_plugin(tmp_path, "b", header="6.9")

    result = run_check("6.8.1", tmp_path)

    assert result.returncode == 1
    assert "a requires WordPress 7.0" in result.stderr
    assert "b requires WordPress 6.9" in result.stderr
