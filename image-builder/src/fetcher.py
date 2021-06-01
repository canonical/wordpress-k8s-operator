#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from typing import Mapping, List
from urllib.parse import urlparse
from yaml import safe_load


zip_plugins_to_get = {
    # please keep these in alphabetical order
    '404page',
    'all-in-one-event-calendar',
    'coschedule-by-todaymade',
    'elementor',
    'essential-addons-for-elementor-lite',
    'favicon-by-realfavicongenerator',
    'feedwordpress',
    'fruitful-shortcodes',
    'genesis-columns-advanced',
    'line-break-shortcode',
    'no-category-base-wpml',
    'openid',
    'post-grid',
    'powerpress',
    'redirection',
    'relative-image-urls',
    'rel-publisher',
    'safe-svg',
    'show-current-template',
    'simple-301-redirects',
    'simple-custom-css',
    'social-media-buttons-toolbar',
    'so-widgets-bundle',
    'svg-support',
    'syntaxhighlighter',
    'wordpress-importer',
    'wordpress-seo',
    'wp-font-awesome',
    'wp-lightbox-2',
    'wp-markdown',
    'wp-mastodon-share',
    'wp-polls',
    'wp-statistics',
}

branch_plugins_to_get = {
    # please keep these in alphabetical order
    'launchpad-integration': {
        'url': 'https://git.launchpad.net/~canonical-sysadmins/wordpress-launchpad-integration/+git/'
               'wordpress-launchpad-integration'
    },
    'openstack-objectstorage': {
        'url': 'https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/openstack-objectstorage-k8s'
    },
    'teams-integration': {
        'url': 'https://git.launchpad.net/~canonical-sysadmins/wordpress-teams-integration/+git/'
               'wordpress-teams-integration'
    },
    'xubuntu-team-members': {
        'url': 'https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-plugin-xubuntu-team-members'
    },
}

branch_themes_to_get = {
    # please keep these in alphabetical order
    'fruitful': {'url': 'https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-fruitful'},
    'light-wordpress-theme': {
        'url': 'https://git.launchpad.net/~canonical-sysadmins/ubuntu-community-webthemes/+git/light-wordpress-theme'
    },
    'mscom': {'url': 'https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-mscom'},
    'thematic': {'url': 'https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-thematic'},
    'twentyeleven': {'url': 'https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-twentyeleven'},
    'ubuntu-cloud-website': {
        'url': 'https://git.launchpad.net/~canonical-sysadmins/ubuntu-cloud-website/+git/ubuntu-cloud-website'
    },
    'ubuntu-community': {
        'url': 'https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-ubuntu-community'
    },
    'ubuntu-community-wordpress-theme': {
        'url': 'https://git.launchpad.net/~canonical-sysadmins/ubuntu-community-wordpress-theme/+git/'
               'ubuntu-community-wordpress-theme'
    },
    'ubuntu-fi-new': {'url': 'https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-ubuntu-fi'},
    'ubuntu-light': {'url': 'https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-ubuntu-light'},
    'ubuntustudio-wp': {
        'url': 'https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-ubuntustudio-wp'
    },
    'wordpress_launchpad': {'url': 'https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-launchpad'},
    'xubuntu-theme': {'url': 'https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-xubuntu-website'},
}


def get_plugins(zip_plugins, branch_plugins):
    total_zips = len(zip_plugins)
    current_zip = 0
    for zip_plugin in zip_plugins:
        current_zip = current_zip + 1
        print('Downloading {} of {} zipped plugins: {} ...'.format(current_zip, total_zips, zip_plugin))
        url = 'https://downloads.wordpress.org/plugin/{}.latest-stable.zip'.format(zip_plugin)
        file_name = os.path.join(os.getcwd(), 'plugins', os.path.basename(url))
        with urllib.request.urlopen(url) as response, open(file_name, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        with zipfile.ZipFile(file_name, 'r') as zip_ref:
            zip_ref.extractall(os.path.join(os.getcwd(), 'plugins'))
        os.remove(file_name)

    total_branches = len(branch_plugins)
    current_branch = 0
    for branch_plugin in branch_plugins:
        current_branch = current_branch + 1
        print('Downloading {} of {} branched plugins: {} ...'.format(current_branch, total_branches, branch_plugin))
        url = branch_plugins[branch_plugin].get('url')
        basename = os.path.basename(url)
        if basename.startswith('lp:'):
            basename = basename[3:]
        if basename.startswith('wp-plugin-'):
            basename = basename[10:]
        dest = os.path.join(os.getcwd(), 'plugins', basename)
        if url.startswith('lp:'):
            cmd = ['bzr', 'branch', url, dest]
        elif url.startswith('https://git'):
            cmd = ['git', 'clone', url, dest]
        else:
            print("ERROR: Don't know how to clone {}".format(url))
            exit(1)
        _ = subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.STDOUT)


def get_themes(branch_themes):
    total_branches = len(branch_themes)
    current_branch = 0
    for branch_theme in branch_themes:
        current_branch = current_branch + 1
        print('Downloading {} of {} branched themes: {} ...'.format(current_branch, total_branches, branch_theme))
        url = branch_themes[branch_theme].get('url')
        basename = os.path.basename(url)
        if basename.startswith('lp:'):
            basename = basename[3:]
        if basename.startswith('wp-theme-'):
            basename = basename[9:]
        dest = os.path.join(os.getcwd(), 'themes/', basename)
        if url.startswith('lp:'):
            cmd = ['bzr', 'branch', url, dest]
        elif url.startswith('https://git'):
            cmd = ['git', 'clone', url, dest]
        else:
            print("ERROR: Don't know how to clone {}".format(url))
            exit(1)
        _ = subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.STDOUT)


class Plugin:
    name: str
    _protocol: str
    _url: str

    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        kwargs = {"name": self.name, "url": self.url}
        return "<Plugin>(name={name}, url={url})".format(**kwargs)

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, url: str):
        u = urlparse(url)
        self._url = u.geturl()
        self._protocol = u.scheme.split("+")[0]
        self._protocol = self._protocol.replace("https", "git")

    def is_available(self):
        print("NOT IMPLEMENTED")

    def is_bzr(self):
        return self._protocol == "lp"

    def is_git(self):
        return self._protocol == "git"

    def sync(self, dest: str):
        self.__make_dest(dest)
        failed = self.__call_sync(os.path.join(dest, self.name))
        if failed:
            raise RuntimeError("failed to sync plugin: {0}".format(self))

    def __make_dest(self, dest: str):
        os.makedirs(dest, mode=0o755, exist_ok=True)

    def __build_cmd(self, dest: str) -> List[str]:
        cmds = {
            "git": ["git", "clone", self.url, dest],
            "lp": ["bzr", "branch", self.url, dest],
        }
        return cmds[self._protocol]

    def __call_sync(self, dest: str, verbose=True):
        subprocess_kwargs = {}
        subprocess_kwargs["universal_newlines"] = True
        if verbose:
            subprocess_kwargs["stderr"] = subprocess.STDOUT

        rv = subprocess.run(self.__build_cmd(dest), **subprocess_kwargs)
        return rv.returncode


def sync_additional_plugins(additional_plugins: Mapping[str, str]):
    """
    Sync any additional WordPress plugins specified from the Container
    environment variable: WORDPRESS_ADDITIONAL_PLUGINS.

    WORDPRESS_ADDITIONAL_PLUGINS must be a valid YAML formatted map string.
    """
    dest_path = os.path.join(os.getcwd(), "plugins")
    total_plugins = len(additional_plugins)
    count = 0
    for name, url in additional_plugins.items():
        count += 1
        plugin = Plugin(name, url)
        print("Syncing {0} of {1} WordPress plugins: {2} ...".format(count, total_plugins, plugin))
        plugin.sync(dest_path)


if __name__ == "__main__":
    if "WORDPRESS_ADDITIONAL_PLUGINS" in os.environ.keys():
        additional_plugins = os.environ["WORDPRESS_ADDITIONAL_PLUGINS"]
        if additional_plugins:
            plugins = safe_load(additional_plugins.encode("utf-8"))
            sync_additional_plugins(plugins)
            # TODO: Script should have command-line flags instead of this.
            print("DEBUG: we are running inside a container, no need to sync base plugins")
        sys.exit(0)
    get_plugins(zip_plugins_to_get, branch_plugins_to_get)
    get_themes(branch_themes_to_get)
