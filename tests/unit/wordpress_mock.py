# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint:disable=invalid-name,protected-access,unused-argument

"""Mocking and patching system for testing WordPress charm."""

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
        self,
        builtin_options: typing.Optional[typing.Dict[str, typing.Union[typing.Dict, str]]] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            builtin_options: some builtin WordPress options come with the WordPress installation.
        """
        self.activated_plugins: typing.Set[str] = set()
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

    def update_option(self, name: str, value: typing.Union[str, dict]) -> None:
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
        builtin_wordpress_options: typing.Optional[
            typing.Dict[str, typing.Union[typing.Dict, str]]
        ] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            builtin_wordpress_options: some builtin WordPress options come with the
                WordPress installation.
        """
        self._databases: typing.Dict[
            typing.Tuple[str, str], typing.Optional[WordPressDatabaseInstanceMock]
        ] = {}
        self._database_credentials: typing.Dict[typing.Tuple[str, str], dict] = {}
        self._builtin_wordpress_options = builtin_wordpress_options

    @staticmethod
    def _database_identifier(host: str, database: str) -> typing.Tuple[str, str]:
        """Create a key for index simulated databases.

        Args:
            host: database host.
            database: database name.

        Returns: host and database
        """
        return host, database

    def prepare_database(self, host: str, database: str, user: str, password: str) -> None:
        """Set up a simulated database, so it can be connected and installed with WordPress.

        Args:
            host: database host.
            database: database name.
            user: database user.
            password: database password.

        Raises:
            KeyError: if database already exists.
        """
        key = self._database_identifier(host, database)
        if key in self._databases:
            raise KeyError(f"Database ({host=!r}, {database=!r} already exists")
        self._databases[key] = None
        self._database_credentials[key] = {"user": user, "password": password}

    def database_can_connect(self, host: str, database: str) -> bool:
        """Test if given host and database can connect to a simulated database.

        Args:
            host: database host.
            database: database name.

        Returns:
            ``True`` if provided host and database name can be used to connect to a simulated
            database, else ``False``.
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

        Returns:
            ``True`` if provided host and database name can be used to connect to a simulated
            database, and the username and the password matches the one for the simulated database.

        Raises:
             KeyError: if no simulated database found with the provided host and database name.
        """
        key = self._database_identifier(host, database)
        if key not in self._database_credentials:
            raise KeyError(f"Database ({host=!r}, {database=!r}) does not exist")
        credential = self._database_credentials[key]
        return credential["user"] == user and credential["password"] == password

    def install_wordpress(self, host: str, database: str) -> None:
        """Install WordPress on a simulated database.

        Args:
            host: database host.
            database: database name.

        Raises:
            KeyError: if database does not exist or WordPress is already installed in the database.
        """
        key = self._database_identifier(host, database)
        if key not in self._databases:
            raise KeyError(f"Database ({host=!r}, {database=!r} does not exist")
        if self._databases[key] is not None:
            raise KeyError(f"Wordpress already installed on ({host=!r}, {database=!r}.")
        self._databases[key] = WordPressDatabaseInstanceMock(
            builtin_options=self._builtin_wordpress_options
        )

    def is_wordpress_installed(self, host: str, database: str) -> bool:
        """Test if WordPress is installed on the given simulated database.

        Args:
            host: database host.
            database: database name.

        Returns: ``True`` if WordPress is installed.

        Raises:
            KeyError: if database does not exist.
        """
        key = self._database_identifier(host, database)
        if key not in self._databases:
            raise KeyError(f"Database ({host=!r}, {database=!r} does not exist")
        return self._databases[key] is not None

    def get_wordpress_database(
        self, host, database
    ) -> typing.Optional[WordPressDatabaseInstanceMock]:
        """Get the simulated WordPress installed database.

        Args:
            host: database host.
            database: database name.

        Returns: The Wordpress database.

        Raises:
            KeyError: if WordPress is not installed in the database.
        """
        key = self._database_identifier(host, database)
        if not self.is_wordpress_installed(host, database):
            raise KeyError(f"Wordpress isn't installed on ({host=!r}, {database=!r}.")
        return self._databases[key]


class MysqlConnectorMock:
    # Mocked Error attribute can be ignored.
    """A mock for :py:mod:`mysql.connector`."""  # noqa: DCO060

    # Mock for :class:`mysql.connector.Error`
    Error = mysql.connector.Error

    def __init__(self, wordpress_database_mock: WordpressDatabaseMock) -> None:
        """Initialize the instance.

        Args:
            wordpress_database_mock: An instance of the WordPress database mock system.
        """
        self._wordpress_database_mock = wordpress_database_mock

    def connect(self, host: str, database: str, user: str, password: str, charset: str):
        """Mock method for :meth:`mysql.connector.connect`.

        Raises:
            Error: if the user can't connect to the database.
        """
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

    def __init__(self) -> None:
        """Initialize the instance."""
        self.registered_handler: typing.List[
            typing.Tuple[typing.Callable[[typing.Sequence[str]], bool], typing.Callable]
        ] = []

    def register(
        self, match: typing.Callable[[typing.Sequence[str]], bool]
    ) -> typing.Callable[[typing.Callable], typing.Callable]:
        """The decorator to collect the match pattern and handler, see class docstring for usage.

        Args:
            match: A match function takes input and output matching result as bool.

        Returns: the decorator.
        """

        def decorator(func):
            """Decorator to collect match pattern and handler.

            Args:
                func: A function takes input and output matching result as bool.

            Returns: the decorator.
            """
            self.registered_handler.append((match, func))
            return func

        return decorator


class ExecProcessMock:
    """A mock for :class:`ops.pebble.ExecProcess`."""

    def __init__(self, return_code: int, stdout: str, stderr: str) -> None:
        """Initialize the instance.

        Args:
            return_code: return code of the mock process run.
            stdout: stdout of the mock process run.
            stderr: stderr of the mock process run.
        """
        self._return_code = return_code
        self._stdout = stdout
        self._stderr = stderr

    def wait_output(self) -> typing.Tuple[str, str]:
        """Mock method for :meth:`ops.pebble.ExecProcess.wait_output`.

        Raises:
            ExecError: if the command execution fails.
        """
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
    _WORDPRESS_VERSION = "5.9.3"

    def __init__(
        self,
        wordpress_database_mock: WordpressDatabaseMock,
    ):
        """Initialize the instance.

        Args:
            wordpress_database_mock: An instance of the WordPress database mock system.
        """
        self.original_pebble = None
        self.fs: typing.Dict[str, str] = {"/proc/mounts": ""}
        self._wordpress_database_mock = wordpress_database_mock
        self.installed_plugins = set(WordpressCharm._WORDPRESS_DEFAULT_PLUGINS)
        self.installed_themes = set(WordpressCharm._WORDPRESS_DEFAULT_THEMES)
        self.wp_eval_history: typing.List[str] = []

    def exec(
        self, cmd, user=None, group=None, working_dir=None, combine_stderr=None, timeout=None
    ):
        """Mock method for :meth:`ops.charm.model.Container.exec`.

        Raises:
            ValueError: if not exactly one handler is registered for the cmd.
        """
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
        """Mock method for :meth:`ops.charm.model.Container.pull`."""
        return io.StringIO(self.fs[path])

    def push(self, path: str, source: str, user=None, group=None, permissions=None) -> None:
        """Mock method for :meth:`ops.charm.model.Container.push`."""
        self.fs[path] = source

    def exists(self, path):
        """Mock method for :meth:`ops.charm.model.Container.exists`."""
        return path in self.fs

    def list_files(self, path: str) -> typing.List[str]:
        """Mock method for :meth:`ops.charm.model.Container.list_files`."""
        if not path.endswith("/"):
            path += "/"
        file_list = []
        for file in self.fs:
            if file.startswith(path):
                file_list.append(file.replace(path, "", 1).split("/")[0])
        return file_list

    def remove_path(self, path: str, recursive: bool = False) -> None:
        # Reraise documentation for mocked path removal can be ignored.
        """Mock method for :meth:`ops.charm.model.Container.remove_path`.

        Raises:
            KeyError: if path is not found in the mock filesystem.
        """  # noqa: DCO055
        try:
            del self.fs[path]
        except KeyError:
            if recursive:
                return
            raise

    def _get_current_database_config(
        self,
    ) -> typing.Optional[typing.Dict[str, str]]:
        """Extract the db connection info from the wp-config.php file in the mock file system.

        Returns:
            A dict with four keys: db_host, db_name, db_user, db_password.

        Raises:
            ValueError: if the db key is not defined exactly once.
        """
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

    def _current_database_host_and_database(self) -> typing.Tuple[str, str]:
        """Extract the db host and name from the wp-config.php file in the mock file system.

        Returns:
            A tuple of database host and database name.

        Raises:
            KeyError: if the database configuration files does not exist.
        """
        db_info = self._get_current_database_config()
        if db_info is None:
            raise KeyError("wp-config.php dose not exist")
        return db_info["db_host"], db_info["db_name"]

    def _current_database(self) -> typing.Optional[WordPressDatabaseInstanceMock]:
        """Retrieve the current connected mock WordPress database instance as in the wp-config.php.

        Returns:
            The current connected mock WordPress database instance as in the wp-config.php.
        """
        return self._wordpress_database_mock.get_wordpress_database(
            *self._current_database_host_and_database()
        )

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "core", "is-installed"])
    def _mock_wp_core_is_installed(self, cmd):
        """Simulate ``wp core is-installed`` command execution in the container."""
        is_installed = self._wordpress_database_mock.is_wordpress_installed(
            *self._current_database_host_and_database()
        )
        return ExecProcessMock(return_code=0 if is_installed else 1, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "core", "install"])
    def _mock_wp_core_install(self, cmd):
        """Simulate ``wp core install`` command execution in the container."""
        self._wordpress_database_mock.install_wordpress(
            *self._current_database_host_and_database()
        )
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "theme", "list"])
    def _mock_wp_theme_list(self, cmd):
        """Simulate ``wp theme list`` command execution in the container."""
        return ExecProcessMock(
            return_code=0,
            stdout=json.dumps([{"name": t} for t in self.installed_themes]),
            stderr="",
        )

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "theme", "install"])
    def _mock_wp_theme_install(self, cmd):
        """Simulate ``wp theme install <theme>`` command execution in the container."""
        theme = cmd[3]
        self.installed_themes.add(theme)
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "theme", "delete"])
    def _mock_wp_theme_delete(self, cmd):
        """Simulate ``wp theme delete <theme>`` command execution in the container."""
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
        """Simulate ``wp plugin list`` command execution in the container."""
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
        """Simulate ``wp plugin install <plugin>`` command execution in the container."""
        plugin = cmd[3]
        self.installed_plugins.add(plugin)
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "plugin", "uninstall"])
    def _mock_wp_plugin_uninstall(self, cmd):
        """Simulate ``wp plugin uninstall <plugin>`` command execution in the container."""
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
        """Simulate ``wp plugin activate <plugin>`` command execution in the container."""
        db = self._current_database()
        plugin = cmd[3]
        if plugin in db.activated_plugins:
            return ExecProcessMock(
                return_code=1, stdout="", stderr="Error, activate an active plugin"
            )
        db.activate_plugin(plugin)
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "plugin", "deactivate"])
    def _mock_wp_plugin_deactivate(self, cmd):
        """Simulate ``wp plugin deactivate <plugin>`` command execution in the container."""
        plugin = cmd[3]
        db = self._current_database()
        if plugin not in db.activated_plugins:
            return ExecProcessMock(
                return_code=1, stdout="", stderr="Error, deactivate an inactive plugin"
            )
        db.deactivate_plugin(plugin)
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "option", "update"])
    def _mock_wp_option_update(self, cmd):
        """Simulate command execution in the container.

        Simulate WordPress option update command which is equivalent to:
        ``wp option update <option> <value> [--format=json]``

        Args:
            cmd: Command to simulate the execution in container.
        """
        db = self._current_database()
        option = cmd[3]
        value = cmd[4]
        if "--format=json" in cmd:
            value = json.loads(value)
        db.update_option(option, value)
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "option", "delete"])
    def _mock_wp_option_delete(self, cmd):
        """Simulate ``wp option delete <option>`` command execution in the container."""
        db = self._current_database()
        option = cmd[3]
        db.delete_option(option)
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:2] == ["wp", "eval"])
    def _mock_wp_eval(self, cmd):
        """Simulate ``wp eval <php_code>`` command execution in the container."""
        php_code = cmd[2]
        self.wp_eval_history.append(php_code)
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[0] == "a2enconf")
    def _mock_a2enconf(self, cmd):
        """Simulate ``a2enconf <conf>`` command execution in the container.

        Raises:
            FileNotFoundError: if the apache configuration file does not exist.
        """
        conf = cmd[1]
        conf_src = f"/etc/apache2/conf-available/{conf}.conf"
        if conf_src not in self.fs:
            raise FileNotFoundError(f"Can't enable a non-existent apache config - {conf}")
        self.fs[f"/etc/apache2/conf-enabled/{conf}.conf"] = self.fs[conf_src]
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[0] == "a2disconf")
    def _mock_a2disconf(self, cmd):
        """Simulate ``a2disconf <conf>`` command execution in the container."""
        conf = cmd[1]
        try:
            del self.fs[f"/etc/apache2/conf-enabled/{conf}.conf"]
        except KeyError:
            pass
        return ExecProcessMock(return_code=0, stdout="", stderr="")

    @_exec_handler.register(lambda cmd: cmd[:3] == ["wp", "core", "version"])
    def _mock_wp_core_version(self, _cmd):
        """Simulate ``wp core version`` command execution in the container."""
        return ExecProcessMock(return_code=0, stdout=self._WORDPRESS_VERSION, stderr="")

    def __getattr__(self, item):
        """Passthrough anything else to :class:`ops.charm.model.Container`.

        The ops testing framework will handle the rest of the simulation, like service start/stop,
            service layer etc.
        """
        return getattr(self.original_pebble, item)


class WordpressPatch:
    """The combined mocking and patching system for WordPress unit tests."""

    def __init__(self) -> None:
        """Initialize the instance."""
        self.database = WordpressDatabaseMock(
            builtin_wordpress_options={"users_can_register": "0"}
        )
        self.container = WordpressContainerMock(wordpress_database_mock=self.database)
        self.mysql_connector = MysqlConnectorMock(wordpress_database_mock=self.database)
        self._patches = []  # type: ignore

    def start(self):
        """Start patching."""
        original_container_method = WordpressCharm._container

        def mock_container(_self):
            """Mocked WordPress container."""
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
