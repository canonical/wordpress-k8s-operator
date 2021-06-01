#!/usr/bin/env python3
import unittest
from unittest.mock import patch

from fetcher import Plugin
from fetcher import sync_additional_plugins


class TestPlugin(unittest.TestCase):
    test_name = "testPlugin"
    test_url = "lp:~testUser/testProject/testBranch"

    def setUp(self):
        test_name = self.test_name
        test_url = self.test_url
        self.plugin = Plugin(test_name, test_url)

    def test__init__(self):
        plugin = Plugin(TestPlugin.test_name, TestPlugin.test_url)
        name = plugin.name
        protocol = plugin._protocol
        url = plugin.url
        self.assertEqual(name, TestPlugin.test_name)
        self.assertEqual(protocol, TestPlugin.test_url.split(":")[0])
        self.assertEqual(url, TestPlugin.test_url)

    def test_is_available(self):
        self.plugin.is_available()

    def test_is_bzr(self):
        self.assertTrue(self.plugin.is_bzr())

    def test_is_git(self):
        self.assertFalse(self.plugin.is_git())

    @patch.object(Plugin, "_Plugin__make_dest")
    @patch.object(Plugin, "_Plugin__call_sync")
    def test_sync(self, mock_call_sync, mock_make_dest):

        mock_call_sync.return_value = None
        self.plugin.sync("test/path")

        assert mock_call_sync.called
        assert mock_make_dest.called

        mock_call_sync.return_value = True
        with self.assertRaises(RuntimeError) as cm:
            self.plugin.sync("test/path")
            self.assertTrue("failed to sync plugin" in str(cm.exception))
