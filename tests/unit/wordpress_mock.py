# Copyright 2022 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

import io
import json
import re
import typing
import unittest.mock

import mysql.connector
import ops
import ops.pebble

from charm import WordpressCharm


class WordPressDatabaseInstanceMock:
    """The simulation of a WordPress installed MySQL database."""

    def __init__(
            self, builtin_options: typing.Optional[typing.Dict[str, typing.Dict | str]] = None
    ):
        """Initialize the instance.

        Args:
            builtin_options: some builtin WordPress options come with the WordPress installation.
        """
        self.activated_plugins = set()
        self.default_theme = ""
        self.activated_theme = self.default_theme
        self.options = {}
        if builtin_options:
            self.options.update(builtin_options)

    def activate_plugin(self, plugin: str) -> None:
        """Simulate activate a WordPress plugin.

        Args:
            plugin: plugin name.
        """
        self.activated_plugins.add(plugin)

    def deactivate_plugin(self, plugin: str) -> None:
        """Simulate deactivate a WordPress plugin.

        Args:
            plugin: plugin name.
        """
        self.activated_plugins.remove(plugin)

    def activate_theme(self, theme: str) -> None:
        """Simulate activate a WordPress theme.

        Args:
            theme: theme name.
        """
        self.activated_theme = theme

    def update_option(self, name: str, value: str | dict) -> None:
        """Simulate update a WordPress option.

        Args:
            name: option name.
            value: option value, which can be a string for PHP string or a dict for PHP array.
        """
        self.options[name] = value

    def delete_option(self, name: str) -> None:
        """Simulate delete a WordPress option.

        Args:
            name: option name.
        """
        try:
            del self.options[name]
        except KeyError:
            pass


class WordpressDatabaseMock:
    """Simulate database interaction like connecting, login, WordPress installation."""

    def __init__(
            self,
            builtin_wordpress_options: typing.Optional[typing.Dict[str, typing.Dict | str]] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            builtin_wordpress_options: some builtin WordPress options come with the
                WordPress installation.
        """
        self._databases = {}
        self._database_credentials = {}
        self._builtin_wordpress_options = builtin_wordpress_options

    @staticmethod
    def _database_identifier(host: str, database: str):
        """Create a key for index simulated databases.

        Args:
            host: database host.
            database: database name.
        """
        return host, database

    def prepare_database(self, host: str, database: str, user: str, password: str) -> None:
        """Set up a simulated database, so it can be connected and installed with WordPress.

        Args:
            host: database host.
            database: database name.
            user: database user.
            password: database password.
        """
        key = self._database_identifier(host, database)
        if key in self._databases:
            raise KeyError(f"Database (host={host}, database={database}) already exists")
        self._databases[key] = None
        self._database_credentials[key] = {"user": user, "password": password}

    def database_can_connect(self, host: str, database: str) -> bool:
        """Test if given host and database can connect to a simulated database.

        Args:
            host: database host.
            database: database name.
        """
        key = self._database_identifier(host, database)
        return key in self._databases

    def database_can_login(self, host: str, database: str, user: str, password: str) -> bool:
        """Test if given database credentials can connect to a simulated database.

        Args:
            host: database host.
            database: database name.
            user: database user.
            password: database password.
        """
        key = self._database_identifier(host, database)
        if key not in self._database_credentials:
            raise KeyError(f"Database (host={host}, database={database}) does not exist")
        credential = self._database_credentials[key]
        return credential["user"] == user and credential["password"] == password

    def install_wordpress(self, host: str, database: str) -> None:
        """Install WordPress on a simulated database.

        Args:
            host: database host.
            database: database name.
        """
        key = self._database_identifier(host, database)
        if key not in self._databases:
            raise KeyError(f"Database (host={host}, database={database}) does not exist")
        if self._databases[key] is not None:
            raise KeyError(f"Wordpress already installed on (host={host}, database={database}).")
        self._databases[key] = WordPressDatabaseInstanceMock(
            builtin_options=self._builtin_wordpress_options
        )

    def is_wordpress_installed(self, host: str, database: str) -> bool:
        """Test if WordPress is installed on the given simulated database.

        Args:
            host: database host.
            database: database name.
        """
        key = self._database_identifier(host, database)
        if key not in self._databases:
            raise KeyError(f"Database (host={host}, database={database}) does not exist")
        return self._databases[key] is not None

    def get_wordpress_database(self, host, database) -> WordPressDatabaseInstanceMock:
        """Get the simulated WordPress installed database.

        Args:
            host: database host.
            database: database name.
        """
        key = self._database_identifier(host, database)
        if not self.is_wordpress_installed(host, database):
            raise KeyError(f"Wordpress isn't installed on (host={host}, database={database}).")
        return self._databases[key]


class MysqlConnectorMock:
    """A mock for :py:mod:`mysql.connector`."""

    Error = mysql.connector.Error

    def __init__(self, wordpress_database_mock: WordpressDatabaseMock):
        self._wordpress_database_mock = wordpress_database_mock

    def connect(self, host: str, database: str, user: str, password: str, charset: str):
        if not self._wordpress_database_mock.database_can_connect(host, database):
            raise self.Error(
                msg=f"Can't connect to MySQL server on '{host}:3306' (2003)",
                errno=2003,
            )
        if not self._wordpress_database_mock.database_can_login(host, database, user, password):
            raise self.Error(
                msg=f"Access denied for user '{host}'@* (using password: *)",
                errno=1045,
            )

        return unittest.mock.MagicMock()


class HandlerRegistry:
    """A utility class that can be used to collect pattern and handler pair using decorator syntax.

    For example::
        registry = HandlerRegistry()

        @registry.register(match=lambda target: target.startswith("a"))
        def handler_func(target):
            print(target)

        match, handler = registry.registered_handler[0]
        match("abc") # => True
        handler("abc") # => print("abc")
    """

    def __init__(self):
        self.registered_handler = []

    def register(
            self, match: typing.Callable[[typing.Sequence[str]], bool]
    ) -> typing.Callable[[typing.Callable], typing.Callable]:
        """The decorator to collector the match pattern and handler, see class docstring for usage.

        Args:
            match: A match function takes input and output matching result as bool.
        """

        def decorator(func):
            self.registered_handler.append((match, func))
            return func

        return decorator


class ExecProcessMock:
    """A mock for :class:`ops.pebble.ExecProcess`."""

    def __init__(self, return_code: int, stdout: str, stderr: str):
        self._return_code = return_code
        self._stdout = stdout
        self._stderr = stderr

    def wait_output(self) -> typing.Tuple[str, str]:
        if self._return_code != 0:
            raise ops.pebble.ExecError(
                [], exit_code=self._return_code, stdout=self._stdout, stderr=self._stderr
            )
        return self._stdout, self._stderr


class WordpressContainerMock:
    """A mock for :class:`ops.charm.model.Container`.

    This will simulate file system and subprocess system inside the WordPress container.
    """
    _exec_handler = HandlerRegistry()

    def __init__(
            self,
            wordpress_database_mock: WordpressDatabaseMock,
    ):
        self.original_pebble = None
        self.fs: typing.Dict[str, str] = {}
        self._wordpress_database_mock = wordpress_database_mock
        self.installed_plugins = set(WordpressCharm._WORDPRESS_DEFAULT_PLUGINS)
        self.installed_themes = set(WordpressCharm._WORDPRESS_DEFAULT_THEMES)
        self.wp_eval_history = []

    def exec(
            self, cmd, user=None, group=None, working_dir=None, combine_stderr=None, timeout=None
    ):
        handler = None
        for match, potential_handler in self._exec_handler.registered_handler:
            is_match = match(cmd)
            if is_match and handler is not None:
                raise ValueError(f"Multiple handlers registered for the same cmd {cmd}")
            if is_match:
                handler = potential_handler
        if handler is None:
            raise ValueError(f"No handler registered for the cmd {cmd}")
        return handler(self, cmd)

    def pull(self, path: str) -> typing.IO[str]:
        return io.StringIO(self.fs[path])

    def push(self, path: str, source: str, user=None, group=None, permissions=None) -> None:
        self.fs[path] = source

    def exists(self, path):
        return path in self.fs

    def list_files(self, path: str) -> typing.List[str]:
        if not path.endswith("/"):
            path += "/"
        file_list = []
        for file in self.fs:
            if file.startswith(path):
                file_list.append(file.removeprefix(path).split("/")[0])
        return file_list

    def remove_path(self, path: str, recursive: bool = False) -> None:
        try:
            del self.fs[path]
        except KeyError:
            if recursive:
                return
            raise

    def _get_current_database_config(self):
        wp_config = self.fs.get(WordpressCharm._WP_CONFIG_PATH)
        if wp_config is None:
            return None
        db_info = {}
        for db_key in ("db_host", "db_name", "db_user", "db_password"):
            db_value = re.findall(f"define\\( '{db_key.upper()}', '([^']+)' \\);", wp_config)
            if not db_value:
                raise ValueError(f"{db_key} is missing in wp-config.php")
            if len(db_value) > 1:
                raise ValueError(f"multiple {db_key} definitions")
            db_info[db_key] = db_value[0]
        return db_info

    def _current_database_host_and_database(self):
        db_info = self._get_current_database_config()
        return db_info["db_host"], db_info["db_name"]

    def _current_database(self):
        return self._wordpress_database_mock.get_wordpress_database(
            *self._current_database_host_and_database()
        )

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "core", "is-installed"])
    def _mock_wp_core_is_installed(self, cmd):
        is_installed = self._wordpress_database_mock.is_wordpress_installed(
            *self._current_database_host_and_database()
        )
        return ExecProcessMock(return_code=0 if is_installed else 1, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "core", "install"])
    def _mock_wp_core_install(self, cmd):
        self._wordpress_database_mock.install_wordpress(
            *self._current_database_host_and_database()
        )
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "theme", "list"])
    def _mock_wp_theme_list(self, cmd):
        return ExecProcessMock(
            return_code=0,
            stdout=json.dumps([{"name": t} for t in self.installed_themes]),
            stderr="",
        )

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "theme", "install"])
    def _mock_wp_theme_install(self, cmd):
        theme = cmd[3]
        self.installed_themes.add(theme)
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "theme", "delete"])
    def _mock_wp_theme_delete(self, cmd):
        theme = cmd[3]
        if theme not in self.installed_themes:
            return ExecProcessMock(
                return_code=1,
                stdout="",
                stderr=f"Error, try to delete a non-existent theme {repr(theme)}",
            )
        self.installed_themes.remove(theme)
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "plugin", "list"])
    def _mock_wp_plugin_list(self, cmd):
        db = self._current_database()
        active_plugins = db.activated_plugins
        return ExecProcessMock(
            return_code=0,
            stdout=json.dumps(
                [
                    {"name": t, "status": "active" if t in active_plugins else "inactive"}
                    for t in self.installed_plugins
                ]
            ),
            stderr="",
        )

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "plugin", "install"])
    def _mock_wp_plugin_install(self, cmd):
        plugin = cmd[3]
        self.installed_plugins.add(plugin)
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "plugin", "uninstall"])
    def _mock_wp_plugin_uninstall(self, cmd):
        plugin = cmd[3]
        if plugin not in self.installed_plugins:
            return ExecProcessMock(
                return_code=1,
                stdout="",
                stderr=f"Error, try to delete a non-existent plugin {repr(plugin)}",
            )
        self.installed_plugins.remove(plugin)
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "plugin", "activate"])
    def _mock_wp_plugin_activate(self, cmd):
        db = self._current_database()
        plugin = cmd[3]
        if plugin in db.activated_plugins:
            return ExecProcessMock(
                return_code=1, stdout="", stderr="Error, activate an active plugin"
            )
        else:
            db.activate_plugin(plugin)
            return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "plugin", "deactivate"])
    def _mock_wp_plugin_deactivate(self, cmd):
        plugin = cmd[3]
        db = self._current_database()
        if plugin not in db.activated_plugins:
            return ExecProcessMock(
                return_code=1, stdout="", stderr="Error, deactivate an inactive plugin"
            )
        else:
            db.deactivate_plugin(plugin)
            return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "option", "update"])
    def _mock_wp_option_update(self, cmd):
        db = self._current_database()
        option = cmd[3]
        value = cmd[4]
        if "--format=json" in cmd:
            value = json.loads(value)
        db.update_option(option, value)
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "option", "delete"])
    def _mock_wp_option_delete(self, cmd):
        db = self._current_database()
        option = cmd[3]
        db.delete_option(option)
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:2] == ["wp", "eval"])
    def _mock_wp_eval(self, cmd):
        php_code = cmd[2]
        self.wp_eval_history.append(php_code)
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[0] == "a2enconf")
    def _mock_a2enconf(self, cmd):
        conf = cmd[1]
        conf_src = f"/etc/apache2/conf-available/{conf}.conf"
        if conf_src not in self.fs:
            raise FileNotFoundError(f"Can't enable a non-existent apache config - {conf}")
        self.fs[f"/etc/apache2/conf-enabled/{conf}.conf"] = self.fs[conf_src]
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[0] == "a2disconf")
    def _mock_a2disconf(self, cmd):
        conf = cmd[1]
        try:
            del self.fs[f"/etc/apache2/conf-enabled/{conf}.conf"]
        except KeyError:
            pass
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    def __getattr__(self, item):
        """Passthrough anything else to :class:`ops.charm.model.Container`.

        The ops testing framework will handle the rest of the simulation, like service start/stop,
            service layer etc.
        """
        return getattr(self.original_pebble, item)


class WordpressPatch:
    """The combined mocking and patching system for WordPress unit tests."""

    def __init__(self):
        self.database = WordpressDatabaseMock(
            builtin_wordpress_options={"users_can_register": "0"}
        )
        self.container = WordpressContainerMock(wordpress_database_mock=self.database)
        self.mysql_connector = MysqlConnectorMock(wordpress_database_mock=self.database)
        self._patches = []

    def start(self):
        """Start patching."""
        original_container_method = WordpressCharm._container

        def mock_container(_self):
            container = original_container_method(_self)
            self.container.original_pebble = container
            return self.container

        self._patches.append(
            unittest.mock.patch.multiple(
                WordpressCharm,
                _container=mock_container,
                _DB_CHECK_INTERVAL=0.001,
                _DB_CHECK_TIMEOUT=0,
            )
        )
        self._patches.append(unittest.mock.patch.multiple(mysql, connector=self.mysql_connector))
        for patch in self._patches:
            patch.start()

    def stop(self):
        """Stop patching."""
        for patch in reversed(self._patches):
            patch.stop()
        self._patches = []
