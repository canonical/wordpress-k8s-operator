import re
import html
import json
import typing
import secrets
import mimetypes

import requests


class WordPressPost(typing.TypedDict):
    id: int
    link: str


class WordpressClient:
    """A very simple WordPress client for test purpose only"""

    @classmethod
    def run_wordpress_functionality_test(cls, host: str, admin_username: str, admin_password: str):
        """Run standard WordPress functionality test suite.

        Args:
            host: ip address or hostname of the WordPress instance.
            admin_username: WordPress admin user username.
            admin_password: WordPress admin user password.
        """
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

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        is_admin: bool,
        use_launchpad_login: bool = False,
    ):
        """Initialize the WordPress JSON API client.

        Args:
            host: ip address or hostname of the WordPress instance.
            username: WordPress user username.
            password: WordPress user password.
            is_admin: If this user is a WordPress admin.
            use_launchpad_login: Use Launchpad OpenID to login instead of WordPress userpass.
        """
        self.host = host
        self.username = username
        self.password = password
        self._session = requests.session()
        self.timeout = 10
        if use_launchpad_login:
            self.login_using_launchpad(username, password)
        else:
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

    def _get(
        self,
        url: str,
        headers: typing.Optional[typing.Dict[str, str]] = None,
        except_status_code: typing.Optional[int] = None,
    ) -> requests.Response:
        """HTTP GET using the instance session.

        The instance session contains user's login session cookies, so this method can assess
        restricted resources on WordPress.

        Args:
            url: Same as the ``url`` argument in :meth:`requests.Session.get`.
            headers: Same as ``url``  in :meth:`requests.Session.get`.
            except_status_code: Except the response http status code,
                raise :exc:`requests.HTTPError` if not match.

        Returns:
            An instance of :class:`requests.Response`.
        """
        response = self._session.get(url, headers=headers, timeout=self.timeout)
        if except_status_code is not None and response.status_code != except_status_code:
            raise requests.HTTPError(f"HTTP status {response.status_code}, URL {url} ")
        return response

    def _post(
        self,
        url: str,
        json: typing.Optional[dict] = None,
        data: typing.Optional[typing.Union[bytes, typing.Dict[str, typing.Any]]] = None,
        headers: typing.Optional[typing.Dict[str, str]] = None,
        except_status_code: typing.Optional[int] = None,
    ) -> requests.Response:
        """HTTP GET using the instance session.

        The instance session contains user's login session cookies, so this method can assess
        restricted resources on WordPress.

        Args:
            url: Same as the ``url`` argument in :meth:`requests.Session.post`.
            json: Same as the ``json`` argument in :meth:`requests.Session.post`.
            data: Same as the ``data`` argument in :meth:`requests.Session.post`.
            headers: Same as the ``url``  in :meth:`requests.Session.post`.
            except_status_code: Except the response http status code,
                raise :exc:`requests.HTTPError` if not match.

        Returns:
            An instance of :class:`requests.Response`.
        """

        response = self._session.post(
            url, json=json, data=data, headers=headers, timeout=self.timeout
        )
        if except_status_code is not None and response.status_code != except_status_code:
            raise requests.HTTPError(f"HTTP status {response.status_code}, URL {url} ")
        return response

    def _login(self) -> bool:
        """Login WordPress with current username and password, set session cookies.

        Returns:
            True if login successfully.
        """
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

    def _set_options_permalink(self) -> None:
        """Set WordPress permalink option to /%postname%/"""
        options_permalink_page = self._get(f"http://{self.host}/wp-admin/options-permalink.php")
        options_permalink_page = options_permalink_page.text
        wp_nonce = re.findall('name="_wpnonce" value="([a-zA-Z0-9]+)"', options_permalink_page)[0]
        self._post(
            f"http://{self.host}/wp-admin/options-permalink.php",
            data={
                "_wpnonce": wp_nonce,
                "_wp_http_referer": "/wp-admin/options-permalink.php",
                "selection": "/%postname%/",
                "permalink_structure": "/%postname%/",
                "submit": "Save Changes",
            },
            except_status_code=200,
        )

    def _gen_wp_rest_nonce(self) -> str:
        """Generate a nonce for WordPress REST API.

        Returns:
            (str) A WordPress nonce for WordPress JSON REST API.
        """
        new_post_page = self._get(f"http://{self.host}/wp-admin/post-new.php")
        new_post_page = new_post_page.text
        nonce = json.loads(re.findall("var wpApiSettings = ([^;]+);", new_post_page)[0])["nonce"]
        return nonce

    def create_post(self, title: str, content: str) -> WordPressPost:
        """Create a WordPress post using wp-json API, return post object.

        Args:
            title (str): Title of the post.
            content (str): Content of the post.

        Returns:
            Post object returned from WordPress REST API.
        """
        response = self._post(
            f"http://{self.host}/wp-json/wp/v2/posts/",
            json={"status": "publish", "title": title, "content": content},
            headers={"X-WP-Nonce": self._gen_wp_rest_nonce()},
            except_status_code=201,
        )
        return response.json()

    def create_comment(self, post_id: int, post_link: str, content: str) -> str:
        """Add a comment to a WordPress post using HTML form, return url link of the new comment.

        Args:
            post_id: ID of the post that the new comment will be attached to.
            post_link: URL of the post that the new comment will be attached to.
            content: Content of the new comment.

        Return:
            (str) URL pointed to the comment created.
        """
        post_page = self._get(post_link)
        nonce = re.findall(
            'name="_wp_unfiltered_html_comment_disabled" value="([a-zA-Z0-9]+)"', post_page.text
        )[0]

        response = self._post(
            f"http://{self.host}/wp-comments-post.php",
            data={
                "comment": content,
                "submit": "Post Comment",
                "comment_post_ID": post_id,
                "comment_parent": "0",
                "_wp_unfiltered_html_comment": nonce,
            },
            except_status_code=200,
        )
        if "Duplicate comment detected" in response.text:
            raise ValueError(f"Duplicate comment detected: {repr(content)}")
        return response.url

    def get_homepage(self) -> str:
        """Get the WordPress homepage source (HTML).

        Returns:
            (str) The WordPress homepage content, HTML.
        """
        return self._get(f"http://{self.host}").text

    def get_post(self, post_link: str) -> str:
        """Get the WordPress blog post page source (HTML).

        Args:
            post_link: URL to the WordPress post.

        Returns:
            (str) The WordPress homepage content, HTML.
        """
        return self._get(post_link).text

    def list_themes(self) -> typing.List[str]:
        """List all installed WordPress theme slugs.

        Return:
            (List[str]) WordPress themes Installed.
        """
        response = self._get(
            f"http://{self.host}/wp-json/wp/v2/themes?per_page=100",
            headers={"X-WP-Nonce": self._gen_wp_rest_nonce()},
            except_status_code=200,
        )
        return [t["stylesheet"] for t in response.json()]

    def list_plugins(self) -> typing.List[str]:
        """List all installed WordPress plugin slugs.

        Return:
            (List[str]) WordPress plugins Installed.
        """
        response = self._get(
            f"http://{self.host}/wp-json/wp/v2/plugins?per_page=100",
            headers={"X-WP-Nonce": self._gen_wp_rest_nonce()},
            except_status_code=200,
        )
        return [p["plugin"].split("/")[0] for p in response.json()]

    def list_comments(
        self, status: str = "approve", post_id: typing.Optional[int] = None
    ) -> typing.List[dict]:
        """List all comments in the WordPress site.

        Args:
            status: WordPress comment status, can be 'hold', 'approve', 'spam', or 'trash'.
            post_id: List all comments attached to the post, None to query the entire site.

        Returns:
            (List[dict]) A list of comment objects returned by WordPress REST API.
        """
        url = f"http://{self.host}/wp-json/wp/v2/comments?status={status}"
        if post_id:
            url += f"&post={post_id}"
        response = self._get(url, headers={"X-WP-Nonce": self._gen_wp_rest_nonce()})
        return response.json()

    def upload_media(
        self, filename: str, content: bytes, mimetype: str = None
    ) -> typing.List[str]:
        """Upload a media file (image/video)

        Args:
            filename: Filename of the media file.
            content: Content of the media file, bytes.
            mimetype: Mimetype of the media file, will infer from the filename if not provided.
        Returns:
             URL of the original image and resized images for the uploaded file on WordPress.
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

    def login_using_launchpad(self, username: str, password: str) -> None:
        """Use Launchpad OpenID to login the WordPress site, require launchpad related plugins.

        Args:
            username: Username of the launchpad account.
            password: Password of the launchpad account.
        """
        login_url = f"http://{self.host}/wp-login.php"
        self._get(login_url)
        openid_redirect = self._post(
            login_url,
            data={
                "launchpad": "Login",
                "redirect_to": f"http://{self.host}/wp-admin/",
                "testcookie": "1",
            },
        )
        openid_args = re.findall(
            '<input type="hidden" name="([^"]+)" value="([^"]+)" />',
            html.unescape(openid_redirect.text),
        )
        openid_args = dict(openid_args)
        login_page = self._post(
            "https://login.launchpad.net/+openid",
            data=openid_args,
        )
        csrf_token = re.findall(
            "<input type='hidden' name='csrfmiddlewaretoken' value='([^']+)' />", login_page.text
        )[0]
        login_link = re.findall(
            '<a id="login-link" data-qa-id="login_link" href="([^"]+)" class="p-link--soft">',
            login_page.text,
        )[0]
        login_url = f"https://login.launchpad.net{login_link}"
        confirm_page = self._post(
            login_url,
            data={
                "csrfmiddlewaretoken": csrf_token,
                "email": username,
                "user-intentions": "login",
                "password": password,
                "continue": "",
                "openid.usernamesecret": "",
            },
            headers={"Referer": login_page.url},
        )
        csrf_token = re.findall(
            "<input type='hidden' name='csrfmiddlewaretoken' value='([^']+)' />", confirm_page.text
        )[0]
        team = re.findall(">Team membership: ([^<]+)<", confirm_page.text)[0]
        self._post(
            confirm_page.url,
            data={
                "csrfmiddlewaretoken": csrf_token,
                "nickname": "on",
                "email": "on",
                "fullname": "on",
                team: "on",
                "ok": "",
                "yes": "",
                "openid.usernamesecret": "",
            },
            headers={"Referer": confirm_page.url},
            except_status_code=200,
        )

    def list_associated_ubuntu_one_accounts(self) -> typing.List[str]:
        """List Ubuntu One accounts OpenID IDs associated with the current WordPress account.

        Returns:
            A list of Ubuntu One account OpenID IDs
            (something like https://login.ubuntu.com/+id/xxxxxxxx).
        """
        openid_setting = self._get(
            f"http://{self.host}/wp-admin/users.php?page=your_openids",
            except_status_code=200,
        )
        return re.findall("<td>(https://login\\.ubuntu\\.com[^<]+)</td>", openid_setting.text)

    def list_roles(self) -> typing.List[str]:
        """List all WordPress roles of the current user.

        Returns:
            WordPress roles as a list of str.
        """
        user_page = self._get(f"http://{self.host}/wp-admin/users.php").text
        emails = re.findall("""data-colname="Email"><a href='mailto:([^']+)'>""", user_page)
        usernames = re.findall('users\\.php">([^<]+)</a>', user_page)
        roles = re.findall('data-colname="Role">([^<]+)</td>', user_page)
        for email, username, role in zip(emails, usernames, roles):
            if email == self.username or username == self.username:
                return [r.strip() for r in role.lower().split(",")]
        raise ValueError(f"User {self.username} not found")


if __name__ == "__main__":
    wp = WordpressClient(
        host="10.1.75.131",
        username="testwwcanonical@proton.me",
        password="vebvip-1syffe-Vecwub",
        is_admin=True,
        use_launchpad_login=True,
    )
    wp.login_using_launchpad(wp.username, wp.password)
    import pprint

    pprint.pp(wp.list_roles())
