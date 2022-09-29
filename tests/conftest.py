import pytest


def pytest_addoption(parser):
    parser.addoption("--openstack-rc", action="store", default="")
