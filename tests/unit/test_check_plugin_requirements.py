# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the rock build check of bundled plugin WordPress requirements."""

import os
import shutil
import subprocess  # nosec B404
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "wordpress_rock" / "check_plugin_requirements.php"
PHP = shutil.which("php")


def make_core(core_dir: Path) -> None:
    """Create a fake WordPress 6.8.1 core with only the functions the checker calls.

    These stand-ins only give the checker something to call. They are not a
    test of WordPress's header parsing: the rock build runs the checker
    against the real core and the real bundled plugins.

    Args:
        core_dir: directory to create the fake core in.
    """
    (core_dir / "wp-includes").mkdir(parents=True)
    (core_dir / "wp-admin" / "includes").mkdir(parents=True)
    (core_dir / "wp-includes" / "plugin.php").write_text(
        "<?php\nfunction apply_filters($hook_name, $value, ...$args) { return $value; }\n",
        encoding="utf-8",
    )
    functions_php = r"""<?php
function _cleanup_header_comment($str) { return trim(preg_replace('/\s*(?:\*\/|\?>).*/', '', $str)); }
function get_file_data($file, $default_headers, $context = '') {
    $file_data = file_get_contents($file, false, null, 0, 8 * 1024);
    $file_data = str_replace("\r", "\n", $file_data);
    foreach ($default_headers as $field => $regex) {
        if (preg_match('/^(?:[ \t]*<\?php)?[ \t\/*#@]*' . preg_quote($regex, '/') . ':(.*)$/mi', $file_data, $match) && $match[1]) {
            $default_headers[$field] = _cleanup_header_comment($match[1]);
        } else {
            $default_headers[$field] = '';
        }
    }
    return $default_headers;
}
function wp_get_wp_version() { return '6.8.1'; }
function is_wp_version_compatible($required) { return empty($required) || version_compare(wp_get_wp_version(), $required, '>='); }
"""
    (core_dir / "wp-includes" / "functions.php").write_text(functions_php, encoding="utf-8")
    (core_dir / "wp-admin" / "includes" / "plugin.php").write_text(
        "<?php\n"
        "function get_plugin_data($plugin_file, $markup = true, $translate = true) {\n"
        "    return get_file_data($plugin_file, array('Name' => 'Plugin Name', 'RequiresWP' => 'Requires at least'), 'plugin');\n"
        "}\n",
        encoding="utf-8",
    )


def make_plugin(
    plugins_dir: Path,
    slug: str,
    header: str | None = None,
    helper: str | None = None,
) -> None:
    """Create a fake plugin directory.

    Args:
        plugins_dir: directory that holds the plugins.
        slug: plugin directory name.
        header: "Requires at least" value in the main plugin file header, if any.
        helper: "Requires at least" value in a helper file with no plugin header, if any.
    """
    plugin = plugins_dir / slug
    plugin.mkdir()
    lines = ["<?php", "/**", f" * Plugin Name: {slug}"]
    if header is not None:
        lines.append(f" * Requires at least: {header}")
    lines.append(" */")
    content = "\n".join(lines) + "\n"
    (plugin / f"{slug}.php").write_text(content, encoding="utf-8")
    if helper is not None:
        (plugin / "helper.php").write_text(
            f"<?php\n * Requires at least: {helper}\n", encoding="utf-8"
        )


def run_check(core_dir: Path, plugins_dir: Path) -> subprocess.CompletedProcess:
    """Run the checker against a fake WordPress core and plugin tree.

    Args:
        core_dir: WordPress core directory.
        plugins_dir: directory that holds the plugins.

    Returns:
        The completed process.
    """
    if PHP is None:
        if os.environ.get("CI"):
            pytest.fail("php is required to run these tests in CI")
        pytest.skip("php is not installed")
    return subprocess.run(  # nosec B603
        [PHP, str(SCRIPT), str(core_dir), str(plugins_dir)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(name="wp")
def wp_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """Create a fake WordPress core with an empty plugins directory.

    Returns:
        The core directory and the plugins directory.
    """
    core = tmp_path / "wordpress"
    plugins = core / "wp-content" / "plugins"
    plugins.mkdir(parents=True)
    make_core(core)
    return core, plugins


def test_compatible_plugins_pass(wp: tuple[Path, Path]):
    """
    arrange: a plugin that needs WordPress 6.8 and one with no requirement.
    act: run the check against WordPress 6.8.1.
    assert: the check passes.
    """
    core, plugins = wp
    make_plugin(plugins, "a", header="6.8")
    make_plugin(plugins, "b")

    assert run_check(core, plugins).returncode == 0


def test_newer_requirement_fails(wp: tuple[Path, Path]):
    """
    arrange: a plugin whose header needs WordPress 7.0.
    act: run the check against WordPress 6.8.1.
    assert: the check fails and names the plugin file and both versions.
    """
    core, plugins = wp
    make_plugin(plugins, "wordpress-seo", header="7.0")

    result = run_check(core, plugins)

    assert result.returncode == 1
    assert (
        "wordpress-seo/wordpress-seo.php requires WordPress 7.0, image has 6.8.1" in result.stderr
    )


def test_helper_file_requirement_is_ignored(wp: tuple[Path, Path]):
    """
    arrange: a plugin that needs 6.8, with a helper file that says 7.0 but has no plugin header.
    act: run the check against WordPress 6.8.1.
    assert: the check passes, since only files with a plugin header are plugins.
    """
    core, plugins = wp
    make_plugin(plugins, "a", header="6.8", helper="7.0")

    assert run_check(core, plugins).returncode == 0


def test_readme_requirement_is_ignored(wp: tuple[Path, Path]):
    """
    arrange: a plugin with no header requirement whose readme.txt says 7.0.
    act: run the check against WordPress 6.8.1.
    assert: the check passes, since WordPress only enforces the plugin header.
    """
    core, plugins = wp
    make_plugin(plugins, "safe-svg")
    (plugins / "safe-svg" / "readme.txt").write_text("Requires at least: 7.0\n", encoding="utf-8")

    assert run_check(core, plugins).returncode == 0


def test_all_failures_are_reported(wp: tuple[Path, Path]):
    """
    arrange: two plugins that need WordPress 7.0 and 6.9.
    act: run the check against WordPress 6.8.1.
    assert: the check fails and names both plugins.
    """
    core, plugins = wp
    make_plugin(plugins, "a", header="7.0")
    make_plugin(plugins, "b", header="6.9")

    result = run_check(core, plugins)

    assert result.returncode == 1
    assert "a/a.php requires WordPress 7.0" in result.stderr
    assert "b/b.php requires WordPress 6.9" in result.stderr


def test_root_level_plugin_is_checked(wp: tuple[Path, Path]):
    """
    arrange: a single-file plugin directly in the plugins directory that needs 7.0.
    act: run the check against WordPress 6.8.1.
    assert: the check fails and names the file.
    """
    core, plugins = wp
    (plugins / "root.php").write_text(
        "<?php\n/**\n * Plugin Name: Root\n * Requires at least: 7.0\n */\n",
        encoding="utf-8",
    )

    result = run_check(core, plugins)

    assert result.returncode == 1
    assert "root.php requires WordPress 7.0" in result.stderr
