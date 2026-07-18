from __future__ import annotations

import pytest

from whytrail import registry
from whytrail.runtime.context import default_graph

pytest_plugins = ["pytester"]  # enables the `pytester` fixture for tests/plugin_contract/test_pytest_plugin.py


@pytest.fixture(autouse=True)
def _clean_whytrail_state():
    """The default graph and the plugin registry are process-lifetime
    singletons by design (ADR §08) -- reset them between tests so one
    test's tracked objects can't leak into another's assertions."""
    default_graph().clear()
    registry.reset()
    yield
    default_graph().clear()
    registry.reset()
