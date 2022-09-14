import re
import json

import requests


class WordpressClient:
    """A very simple WordPress client for test purpose only"""

    def __init__(self, host: str, username: str, password: str, is_admin: bool):
        self.host = host
        self.username = username
        self.password = password
        self._session = requests.session()
        self.timeout = 10
        self._login()
        try:
            self._session.get(
                f"http://{self.host}/wp-json/",
                timeout=self.timeout
            ).json()
        except requests.exceptions.JSONDecodeError:
            if not is_admin:
                raise ValueError("set options-permalink manually or login with an admin account")
            self._set_options_permalink()

    def _login(self):
        self._session.get(
            f"http://{self.host}/wp-login.php",
            timeout=self.timeout
        )
        response = self._session.post(
            f"http://{self.host}/wp-login.php",
            data={
                "log": self.username,
                "pwd": self.password,
                "wp-submit": "Log In",
                "redirect_to": f"http://{self.host}/wp-admin/",
                "testcookie": 1
            },
            timeout=self.timeout
        )
        assert (
                response.status_code == 200 and response.url == f"http://{self.host}/wp-admin/"
        ), f"user {self.username} should be able to login WordPress"

    def _set_options_permalink(self):
        options_permalink_page = self._session.get(
            f"http://{self.host}/wp-admin/options-permalink.php",
            timeout=self.timeout
        )
        options_permalink_page = options_permalink_page.text
        wp_nonce = re.findall('name="_wpnonce" value="([a-zA-Z0-9]+)"', options_permalink_page)[0]
        response = self._session.post(
            f"http://{self.host}/wp-admin/options-permalink.php",
            data={
                '_wpnonce': wp_nonce,
                '_wp_http_referer': '/wp-admin/options-permalink.php',
                'selection': '/%postname%/',
                'permalink_structure': '/%postname%/',
                'submit': 'Save Changes'
            },
            timeout=self.timeout
        )

        assert (
                response.status_code == 200
        ), "admin user should able to set WordPress options-permalink to /%postname%/"

    def create_post(self, title: str, content: str):
        new_post_page = self._session.get(
            f"http://{self.host}/wp-admin/post-new.php",
            timeout=self.timeout
        )
        new_post_page = new_post_page.text
        nonce = json.loads(re.findall('var wpApiSettings = ([^;]+);', new_post_page)[0])["nonce"]
        response = self._session.post(
            f"http://{self.host}/wp-json/wp/v2/posts/",
            json={
                "status": "publish",
                "title": title,
                "content": content
            },
            headers={"X-WP-Nonce": nonce},
            timeout=self.timeout
        )
        assert (
                response.status_code == 201
        ), f"User {self.username} should be able to create a post"
        return response.json()

    def create_comment(self, post_id: int, post_link: str, content: str):
        post_page = self._session.get(post_link)
        nonce = re.findall(
            'name="_wp_unfiltered_html_comment_disabled" value="([a-zA-Z0-9]+)"',
            post_page.text
        )[0]

        response = self._session.post(
            f"http://{self.host}/wp-comments-post.php",
            data={
                'comment': content,
                'submit': 'Post Comment',
                'comment_post_ID': post_id,
                'comment_parent': '0',
                '_wp_unfiltered_html_comment': nonce
            },
            timeout=self.timeout
        )
        if "Duplicate comment detected" in response.text:
            raise ValueError(f"Duplicate comment detected: {repr(content)}")
        assert (
                response.status_code == 200 and
                response.url.startswith(post_link)
        ), f"user {self.username} should be able to create comments"
        return response.text

    def get_homepage(self):
        return self._session.get(f"http://{self.host}", timeout=self.timeout).text

    def get_post(self, post_link: str):
        return self._session.get(post_link, timeout=self.timeout).text
