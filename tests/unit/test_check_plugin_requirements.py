# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the rock build check of bundled plugin WordPress requirements."""

import shutil
import subprocess  # nosec B404
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "wordpress_rock" / "check_plugin_requirements.php"
PHP = shutil.which("php")


def make_core(core_dir: Path, version: str = "6.8.1") -> None:
    """Create the small WordPress-core surface used by the checker."""
    (core_dir / "wp-includes").mkdir(parents=True)
    (core_dir / "wp-admin" / "includes").mkdir(parents=True)
    (core_dir / "wp-includes" / "plugin.php").write_text(
        "<?php\n"
        "function apply_filters($hook_name, $value, ...$args) { return $value; }\n",
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
function wp_get_wp_version() { return '__VERSION__'; }
function is_wp_version_compatible($required) { return empty($required) || version_compare(wp_get_wp_version(), $required, '>='); }
""".replace('__VERSION__', version)
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
    late_header: str | None = None,
) -> None:
    """Create a fake plugin directory."""
    plugin = plugins_dir / slug
    plugin.mkdir()
    lines = ["<?php", "/**", f" * Plugin Name: {slug}"]
    if header is not None:
        lines.append(f" * Requires at least: {header}")
    lines.append(" */")
    content = "\n".join(lines) + "\n"
    if late_header is not None:
        content += "x" * (8 * 1024) + f"\n * Requires at least: {late_header}\n"
    (plugin / f"{slug}.php").write_text(content, encoding="utf-8")
    if helper is not None:
        (plugin / "helper.php").write_text(f"<?php\n * Requires at least: {helper}\n", encoding="utf-8")


def run_check(core_dir: Path, plugins_dir: Path) -> subprocess.CompletedProcess:
    """Run the checker against a fake WordPress core and plugin tree."""
    if PHP is None:
        pytest.skip("php is not installed")
    return subprocess.run(  # nosec B603
        [PHP, str(SCRIPT), str(core_dir), str(plugins_dir)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_compatible_plugins_pass(tmp_path: Path):
    core = tmp_path / "wordpress"
    plugins = core / "wp-content" / "plugins"
    plugins.mkdir(parents=True)
    make_core(core)
    make_plugin(plugins, "a", header="6.8")
    make_plugin(plugins, "b")

    assert run_check(core, plugins).returncode == 0


def test_newer_requirement_fails(tmp_path: Path):
    core = tmp_path / "wordpress"
    plugins = core / "wp-content" / "plugins"
    plugins.mkdir(parents=True)
    make_core(core)
    make_plugin(plugins, "wordpress-seo", header="7.0")

    result = run_check(core, plugins)

    assert result.returncode == 1
    assert "wordpress-seo/wordpress-seo.php requires WordPress 7.0, image has 6.8.1" in result.stderr


def test_helper_file_requirement_is_ignored(tmp_path: Path):
    core = tmp_path / "wordpress"
    plugins = core / "wp-content" / "plugins"
    plugins.mkdir(parents=True)
    make_core(core)
    make_plugin(plugins, "a", header="6.8", helper="7.0")

    assert run_check(core, plugins).returncode == 0


def test_header_after_first_eight_kib_is_ignored(tmp_path: Path):
    core = tmp_path / "wordpress"
    plugins = core / "wp-content" / "plugins"
    plugins.mkdir(parents=True)
    make_core(core)
    make_plugin(plugins, "a", header="6.8", late_header="7.0")

    assert run_check(core, plugins).returncode == 0


def test_readme_requirement_is_ignored(tmp_path: Path):
    core = tmp_path / "wordpress"
    plugins = core / "wp-content" / "plugins"
    plugins.mkdir(parents=True)
    make_core(core)
    make_plugin(plugins, "safe-svg")
    (plugins / "safe-svg" / "readme.txt").write_text("Requires at least: 7.0\n", encoding="utf-8")

    assert run_check(core, plugins).returncode == 0


def test_numeric_version_compare(tmp_path: Path):
    core = tmp_path / "wordpress"
    plugins = core / "wp-content" / "plugins"
    plugins.mkdir(parents=True)
    make_core(core, version="6.9")
    make_plugin(plugins, "a", header="6.10")

    assert run_check(core, plugins).returncode == 1


def test_three_part_requirement_equal_to_wp_passes(tmp_path: Path):
    core = tmp_path / "wordpress"
    plugins = core / "wp-content" / "plugins"
    plugins.mkdir(parents=True)
    make_core(core)
    make_plugin(plugins, "a", header="6.8.1")

    assert run_check(core, plugins).returncode == 0


def test_crlf_requirement_is_parsed(tmp_path: Path):
    core = tmp_path / "wordpress"
    plugins = core / "wp-content" / "plugins"
    plugins.mkdir(parents=True)
    make_core(core)
    make_plugin(plugins, "a", header="7.0\r")

    result = run_check(core, plugins)

    assert result.returncode == 1
    assert "a/a.php requires WordPress 7.0, image has 6.8.1" in result.stderr


def test_all_failures_are_reported(tmp_path: Path):
    core = tmp_path / "wordpress"
    plugins = core / "wp-content" / "plugins"
    plugins.mkdir(parents=True)
    make_core(core)
    make_plugin(plugins, "a", header="7.0")
    make_plugin(plugins, "b", header="6.9")

    result = run_check(core, plugins)

    assert result.returncode == 1
    assert "a/a.php requires WordPress 7.0" in result.stderr
    assert "b/b.php requires WordPress 6.9" in result.stderr


def test_root_level_plugin_is_checked(tmp_path: Path):
    core = tmp_path / "wordpress"
    plugins = core / "wp-content" / "plugins"
    plugins.mkdir(parents=True)
    make_core(core)
    (plugins / "root.php").write_text(
        "<?php\n/**\n * Plugin Name: Root\n * Requires at least: 7.0\n */\n",
        encoding="utf-8",
    )

    result = run_check(core, plugins)

    assert result.returncode == 1
    assert "root.php requires WordPress 7.0" in result.stderr
