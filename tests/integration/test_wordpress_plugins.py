#!/usr/bin/env python3
import os
import requests
import unittest
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver import FirefoxProfile
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def read_secret(filen, mode="r"):
    with open(os.path.join(os.environ["WORKSPACE"], filen), mode) as f:
        return f.read()


AUTH_TOKEN = str(read_secret("auth_token.txt")).rstrip()
MAXIMUM_PAGE_LOAD_TIME = 15
SSO_PASSWORD = str(read_secret("sso_password.txt")).rstrip()
TEST_IMAGE = read_secret("test.png", mode="rb")


class WordpressIntegrationTest(unittest.TestCase):
    def _wordpress_sso_login(self):
        self.driver.get("https://ci-blog.admin.canonical.com/wp-admin")
        self.assertIn("Log In", self.driver.title)
        elem = self.driver.find_element_by_id("lplogin")
        elem.send_keys(Keys.RETURN)
        WebDriverWait(self.driver, MAXIMUM_PAGE_LOAD_TIME).until(EC.presence_of_element_located((By.ID, "id_email")))
        elem = self.driver.find_element_by_id("id_email")
        elem.send_keys("webops+wordpress-ci@canonical.com")
        elem = self.driver.find_element_by_id("id_password")
        elem.send_keys(SSO_PASSWORD)
        elem = self.driver.find_element_by_name("continue")
        elem.send_keys(Keys.RETURN)
        WebDriverWait(self.driver, MAXIMUM_PAGE_LOAD_TIME).until(EC.presence_of_element_located((By.NAME, "yes")))
        elem = self.driver.find_element_by_id("id_wordpress-k8s-ci")
        if not elem.is_selected():
            ActionChains(self.driver).move_to_element(elem).click().perform()
        elem = self.driver.find_element_by_name("yes")
        elem.send_keys(Keys.RETURN)
        WebDriverWait(self.driver, MAXIMUM_PAGE_LOAD_TIME).until(EC.title_contains(("Dashboard")))

    def setUp(self):
        profile = FirefoxProfile()
        profile.accept_untrusted_certs = True
        options = Options()
        options.headless = True
        self.driver = webdriver.Firefox(service_log_path="/dev/null", options=options, firefox_profile=profile)

    def test_wordpress_signin(self):
        self._wordpress_sso_login()
        self.assertIn("Dashboard", self.driver.title)

    def test_wordpress_akismit(self):
        self._wordpress_sso_login()
        self.driver.get("https://ci-blog.admin.canonical.com/wp-admin/options-general.php?page=akismet-key-config")
        elem = self.driver.find_element_by_id("delete-action")
        self.assertEqual("Disconnect this account", elem.text)

    def test_swift_integration_content_rendering(self):
        data = TEST_IMAGE
        headers = {
            "Authorization": "Basic {}".format(AUTH_TOKEN),
            "content-disposition": "attachment; filename=test.png",
            "content-type": "image/png",
        }
        resp = requests.post(
            url="https://ci-blog.admin.canonical.com/wp-json/wp/v2/media/", data=data, headers=headers, verify=False
        )

        headers = {
            "Authorization": "Basic {}".format(AUTH_TOKEN),
        }
        resp = requests.post(
            url="https://ci-blog.admin.canonical.com/wp-json/wp/v2/posts",
            data={"title": "Test Post", "content": resp.json()["description"]["rendered"], "status": "publish"},
            headers=headers,
            verify=False,
        )
        self.driver.get(resp.json()["guid"]["raw"])
        elem = self.driver.find_element_by_xpath('//p[@class="attachment"]/a/img')
        self.assertIn("test.png", elem.get_attribute("src"))

    def tearDown(self):
        self.driver.close()


if __name__ == "__main__":
    unittest.main()
