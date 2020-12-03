#!/usr/bin/python3

import logging
import os
import subprocess
import urllib.request
from time import sleep
from yaml import safe_load

helpers_path = "/srv/wordpress-helpers"
install_path = "/var/www/html"


def call_php_helper(helper, stdin="", *args):
    path = os.path.join(helpers_path, helper)
    cmd = ["php", path]
    cmd.extend([str(arg) for arg in args])
    logging.info(cmd)
    process = subprocess.Popen(
        cmd,
        cwd=install_path,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return process.communicate(stdin)[0]  # spit back stdout+stderr combined


def enable_plugin(*plugins):
    logging.info("Enabling plugins: {}".format(plugins))
    logging.info(call_php_helper("_enable_plugin.php", "", *plugins))


def get_option(key):
    value = call_php_helper("_get_option.php", "", key)
    return safe_load(value)


def add_option(key, value):
    # Ensure we don't overwrite settings
    if not get_option(key):
        logging.info("Adding option: {}".format(key))
        call_php_helper("_add_option.php", "", key, value)
    else:
        logging.info('Option "{}" already in place, skipping.'.format(key))


def encode_team_map(team_map):
    # example: site-sysadmins=administrator,site-editors=editor,site-executives=editor
    team_map_lines = []
    i = 0
    team_map_lines.append("a:{}:{{".format(len(team_map.split(","))))
    for mapping in team_map.split(","):
        i = i + 1
        team, role = mapping.split("=", 2)
        team_map_lines.append("i:{};".format(i))
        team_map_lines.append('O:8:"stdClass":4:{')
        team_map_lines.append('s:2:"id";')
        team_map_lines.append("i:{};".format(i))
        team_map_lines.append('s:4:"team";')
        team_map_lines.append('s:{}:"{}";'.format(len(team), team))
        team_map_lines.append('s:4:"role";')
        team_map_lines.append('s:{}:"{}";'.format(len(role), role))
        team_map_lines.append('s:6:"server";')
        team_map_lines.append('s:1:"0";')
        team_map_lines.append("}")
    team_map_lines.append("}")

    return "".join(team_map_lines)


def enable_akismet(key):
    enable_plugin("akismet/akismet.php")
    add_option("akismet_strictness", "0")
    add_option("akismet_show_user_comments_approved", "0")
    add_option("wordpress_api_key", key)


def enable_openid(team_map):
    encoded_team_map = encode_team_map(team_map)
    enable_plugin("openid/openid.php")
    add_option("openid_required_for_registration", "1")
    add_option("openid_teams_trust_list", encoded_team_map)


def enable_swift(swift_config):
    enable_plugin("openstack-objectstorage/objectstorage.php")
    for k, v in swift_config.items():
        add_option("object_storage_{}".format(k), v)


def configure_wordpress():
    url = "http://localhost"
    sleep_time = 10
    total_sleep_time = 0
    max_sleep_time = 600
    success = False
    while success is not True:
        if total_sleep_time > max_sleep_time:
            return False
        try:
            response = urllib.request.urlopen(url, timeout=sleep_time)
        except Exception:
            logging.info("Waiting for Wordpress to accept connections")
            sleep(sleep_time)
            total_sleep_time = total_sleep_time + sleep_time
        else:
            if response.status == 200:
                success = True
            else:
                logging.info(
                    "Waiting for Wordpress to return HTTP 200 (got {})".format(
                        response.status
                    )
                )
                sleep(sleep_time)
    return True


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logging.basicConfig(
        filename="/var/log/wordpress-plugin-handler.log", level=logging.DEBUG
    )

    if configure_wordpress():
        # create the file to satisfy the readinessProbe
        open(os.path.join(helpers_path, '.ready'), 'a').close()

        key = os.getenv("WP_PLUGIN_AKISMET_KEY")
        if key:
            enable_akismet(key)

        team_map = os.getenv("WP_PLUGIN_OPENID_TEAM_MAP")
        if team_map:
            enable_openid(team_map)

        swift_url = os.getenv("SWIFT_URL")
        if swift_url:
            swift_config = {}
            swift_config['url'] = swift_url
            swift_config['auth_url'] = os.getenv("SWIFT_AUTH_URL")
            swift_config['bucket'] = os.getenv("SWIFT_BUCKET")
            swift_config['password'] = os.getenv("SWIFT_PASSWORD")
            swift_config['prefix'] = os.getenv("SWIFT_PREFIX")
            swift_config['region'] = os.getenv("SWIFT_REGION")
            swift_config['tenant'] = os.getenv("SWIFT_TENANT")
            swift_config['username'] = os.getenv("SWIFT_USERNAME")
            swift_config['copy_to_swift'] = os.getenv("SWIFT_COPY_TO_SWIFT")
            swift_config['serve_from_swift'] = os.getenv("SWIFT_SERVE_FROM_SWIFT")
            swift_config['remove_local_file'] = os.getenv("SWIFT_REMOVE_LOCAL_FILE")
            enable_swift(swift_config)
