import re
import json
import secrets
import mimetypes
import typing

import requests


class WordpressClient:
    """A very simple WordPress client for test purpose only"""

    @classmethod
    def run_wordpress_functionality_test(cls, host: str, admin_username: str, admin_password: str):
        """Run standard WordPress functionality test suite"""
        wp_client = cls(host=host, username=admin_username, password=admin_password, is_admin=True)
        post_title = secrets.token_hex(16)
        post_content = secrets.token_hex(16)
        post = wp_client.create_post(
            title=post_title,
            content=post_content,
        )
        homepage = wp_client.get_homepage()
        assert (
            post_title in homepage and post_content in homepage
        ), "admin user should be able to create a new post"
        comment = secrets.token_hex(16)
        post_link = post["link"]
        comment_link = wp_client.create_comment(
            post_id=post["id"],
            post_link=post_link,
            content=comment,
        )
        assert comment_link.startswith(post_link) and comment in wp_client.get_post(
            post_link
        ), "admin user should be able to create a comment"

    def __init__(self, host: str, username: str, password: str, is_admin: bool):
        self.host = host
        self.username = username
        self.password = password
        self._session = requests.session()
        self.timeout = 10
        if not self._login():
            raise RuntimeError(f"login failed with username {username}")
        # By default, WordPress does not expose the /wp-json/ endpoint test if /wp-json
        # is exposed, and expose that with a permalink setting if not
        try:
            self._get(f"http://{self.host}/wp-json/").json()
        except requests.exceptions.JSONDecodeError:
            if not is_admin:
                raise ValueError("set options-permalink manually or login with an admin account")
            self._set_options_permalink()

    def _get(self, url: str, headers=None, except_status_code=None):
        """HTTP GET using the instance session"""
        response = self._session.get(url, headers=headers, timeout=self.timeout)
        if except_status_code is not None and response.status_code != except_status_code:
            raise requests.HTTPError(f"HTTP status {response.status_code}, URL {url} ")
        return response

    def _post(self, url: str, json=None, data=None, headers=None, except_status_code=None):
        """HTTP GET using the instance session"""
        response = self._session.post(
            url, json=json, data=data, headers=headers, timeout=self.timeout
        )
        if except_status_code is not None and response.status_code != except_status_code:
            raise requests.HTTPError(f"HTTP status {response.status_code}, URL {url} ")
        return response

    def _login(self):
        """Login WordPress with current username and password, set session cookies"""
        self._get(f"http://{self.host}/wp-login.php")
        response = self._post(
            f"http://{self.host}/wp-login.php",
            data={
                "log": self.username,
                "pwd": self.password,
                "wp-submit": "Log In",
                "redirect_to": f"http://{self.host}/wp-admin/",
                "testcookie": 1,
            },
            except_status_code=200,
        )
        return response.url == f"http://{self.host}/wp-admin/"

    def _set_options_permalink(self):
        """Set WordPress permalink option to /%postname%/"""
        options_permalink_page = self._get(f"http://{self.host}/wp-admin/options-permalink.php")
        options_permalink_page = options_permalink_page.text
        wp_nonce = re.findall('name="_wpnonce" value="([a-zA-Z0-9]+)"', options_permalink_page)[0]
        self._post(
            f"http://{self.host}/wp-admin/options-permalink.php",
            data={
                '_wpnonce': wp_nonce,
                '_wp_http_referer': '/wp-admin/options-permalink.php',
                'selection': '/%postname%/',
                'permalink_structure': '/%postname%/',
                'submit': 'Save Changes',
            },
            except_status_code=200,
        )

    def _gen_wp_rest_nonce(self):
        """Generate a nonce for WordPress REST API"""
        new_post_page = self._get(f"http://{self.host}/wp-admin/post-new.php")
        new_post_page = new_post_page.text
        nonce = json.loads(re.findall('var wpApiSettings = ([^;]+);', new_post_page)[0])["nonce"]
        return nonce

    def create_post(self, title: str, content: str):
        """Create a WordPress post using wp-json API, return post object"""
        response = self._post(
            f"http://{self.host}/wp-json/wp/v2/posts/",
            json={"status": "publish", "title": title, "content": content},
            headers={"X-WP-Nonce": self._gen_wp_rest_nonce()},
            except_status_code=201,
        )
        return response.json()

    def create_comment(self, post_id: int, post_link: str, content: str):
        """Add a comment to a WordPress post using HTML form, return url link of the new comment"""
        post_page = self._get(post_link)
        nonce = re.findall(
            'name="_wp_unfiltered_html_comment_disabled" value="([a-zA-Z0-9]+)"', post_page.text
        )[0]

        response = self._post(
            f"http://{self.host}/wp-comments-post.php",
            data={
                'comment': content,
                'submit': 'Post Comment',
                'comment_post_ID': post_id,
                'comment_parent': '0',
                '_wp_unfiltered_html_comment': nonce,
            },
            except_status_code=200,
        )
        if "Duplicate comment detected" in response.text:
            raise ValueError(f"Duplicate comment detected: {repr(content)}")
        return response.url

    def get_homepage(self):
        """Get the WordPress homepage source (HTML) as string"""
        return self._get(f"http://{self.host}").text

    def get_post(self, post_link: str):
        """Get the WordPress blog post page source (HTML) as string"""
        return self._get(post_link).text

    def list_themes(self):
        """List all installed WordPress theme slugs"""
        response = self._get(
            f"http://{self.host}/wp-json/wp/v2/themes?per_page=100",
            headers={"X-WP-Nonce": self._gen_wp_rest_nonce()},
            except_status_code=200,
        )
        return [t["stylesheet"] for t in response.json()]

    def list_plugins(self):
        """List all installed WordPress plugin slugs"""
        response = self._get(
            f"http://{self.host}/wp-json/wp/v2/plugins?per_page=100",
            headers={"X-WP-Nonce": self._gen_wp_rest_nonce()},
            except_status_code=200,
        )
        return [p["plugin"].split("/")[0] for p in response.json()]

    def list_comments(self, status='approve', post_id: int = None):
        """List all comments in the WordPress site"""
        url = f"http://{self.host}/wp-json/wp/v2/comments?status={status}"
        if post_id:
            url += f"&post={post_id}"
        response = self._get(url, headers={"X-WP-Nonce": self._gen_wp_rest_nonce()})
        return response.json()

    def upload_media(self, filename: str, content: bytes, mimetype: str = None) -> typing.List[str]:
        """Upload a media file (image/video)

        Return URL of the original image and resized images for the uploaded file on WordPress.
        """
        if mimetype is None:
            mimetype = mimetypes.guess_type(filename)[0]
        if mimetype is None:
            raise ValueError("Unable to deduce mimetype from filename")
        response = self._post(
            f"http://{self.host}/wp-json/wp/v2/media",
            headers={
                "X-WP-Nonce": self._gen_wp_rest_nonce(),
                "Content-Type": mimetype,
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
            data=content,
            except_status_code=201,
        )
        media = response.json()
        image_urls = []
        for size in media["media_details"]["sizes"].values():
            image_urls.append(size["source_url"])
        if media["source_url"] not in image_urls:
            image_urls.append(media["source_url"])
        return image_urls

    def associate_ubuntu_one(self, username, password):
        openid_setting_url = f"http://{self.host}/wp-admin/users.php?page=your_openids"
        openid_setting_page = self._get(openid_setting_url)
        nonce = re.findall(
            '<input type="hidden" id="_wpnonce" name="_wpnonce" value="([^"]+)" />',
            openid_setting_page.text,
        )[1]
        openid_redirect = self._post(
            openid_setting_url,
            data={
                'openid_identifier': 'login.ubuntu.com',
                '_wpnonce': nonce,
                '_wp_http_referer': '/wp-admin/users.php?page=your_openids',
                'action': 'add',
            },
        )
        openid_args = re.findall(
            '<input type="hidden" name="([^"]+)" value="([^"]+)" />', openid_redirect.text
        )
        openid_args = dict(openid_args)
        login_page = self._post(
            "https://login.ubuntu.com/+openid",
            data=openid_args,
        )
        csrf_token = re.findall(
            "<input type='hidden' name='csrfmiddlewaretoken' value='([^']+)' />", login_page.text
        )[0]
        login_link = re.findall(
            '<a id="login-link" data-qa-id="login_link" href="([^"]+)" class="p-link--soft">',
            login_page.text,
        )[0]
        login_url = "https://login.ubuntu.com" + login_link
        confirm_page = self._post(
            login_url,
            data={
                'csrfmiddlewaretoken': csrf_token,
                'email': username,
                'user-intentions': 'login',
                'password': password,
                'continue': '',
                'openid.usernamesecret': '',
            },
            headers={"Referer": login_page.url},
        )
        csrf_token = re.findall(
            "<input type='hidden' name='csrfmiddlewaretoken' value='([^']+)' />", confirm_page.text
        )[0]
        self._post(
            confirm_page.url,
            data={
                'csrfmiddlewaretoken': csrf_token,
                'nickname': 'on',
                'email': 'on',
                'fullname': 'on',
                'ok': '',
                'yes': '',
                'openid.usernamesecret': '',
            },
            headers={"Referer": confirm_page.url},
            except_status_code=200,
        )

    def list_associated_ubuntu_one_accounts(self):
        openid_setting = self._get(
            f"http://{self.host}/wp-admin/users.php?page=your_openids",
            except_status_code=200,
        )
        return re.findall("<td>(https://login\\.ubuntu\\.com[^<]+)</td>", openid_setting.text)
