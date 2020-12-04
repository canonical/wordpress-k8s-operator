#!/usr/bin/env python3

import os
import shutil
import subprocess
import urllib.request
import zipfile


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
        file_name = os.path.join(os.getcwd(), 'files/plugins', os.path.basename(url))
        with urllib.request.urlopen(url) as response, open(file_name, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        with zipfile.ZipFile(file_name, 'r') as zip_ref:
            zip_ref.extractall(os.path.join(os.getcwd(), 'files/plugins'))
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
        dest = os.path.join(os.getcwd(), 'files/plugins', basename)
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
        dest = os.path.join(os.getcwd(), 'files/themes/', basename)
        if url.startswith('lp:'):
            cmd = ['bzr', 'branch', url, dest]
        elif url.startswith('https://git'):
            cmd = ['git', 'clone', url, dest]
        else:
            print("ERROR: Don't know how to clone {}".format(url))
            exit(1)
        _ = subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.STDOUT)


if __name__ == '__main__':
    get_plugins(zip_plugins_to_get, branch_plugins_to_get)
    get_themes(branch_themes_to_get)
