"""Paid provider tests require an explicit CLI opt-in."""
import pytest


def pytest_addoption(parser):
    parser.addoption('--live',action='store_true',default=False,
                     help='Run paid provider checks using local .env credentials.')


def pytest_configure(config):
    config.addinivalue_line('markers','live: paid provider integration; requires --live')


def pytest_collection_modifyitems(config,items):
    if not config.getoption('--live'):
        for item in items:
            if 'live' in item.keywords:
                item.add_marker(pytest.mark.skip(reason='Paid API test disabled; explicitly select with --live'))
