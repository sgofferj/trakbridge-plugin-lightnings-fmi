# pylint: disable=wrong-import-position, protected-access
import sys
from unittest.mock import MagicMock
from typing import Dict, Any

# Mock trakbridge imports
mock_base_plugin = MagicMock()
mock_logging_service = MagicMock()

sys.modules["plugins.base_plugin"] = mock_base_plugin
sys.modules["services.logging_service"] = mock_logging_service


# Define mock classes/functions needed for import
# pylint: disable=too-few-public-methods
class MockBaseGPSPlugin:
    """Mock BaseGPSPlugin"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def get_decrypted_config(self) -> Dict[str, Any]:
        """Mock get_decrypted_config"""
        return self.config


class MockPluginConfigField:
    """Mock PluginConfigField"""

    def __init__(self, **kwargs: Any):
        for key, value in kwargs.items():
            setattr(self, key, value)


mock_base_plugin.BaseGPSPlugin = MockBaseGPSPlugin
mock_base_plugin.PluginConfigField = MockPluginConfigField

from plugin.fmi_lightnings import FMILightningsPlugin


def test_plugin_metadata() -> None:
    """Test plugin metadata"""
    config: Dict[str, Any] = {"history": 300}
    plugin = FMILightningsPlugin(config)

    metadata = plugin.plugin_metadata
    assert metadata["display_name"] == "FMI Lightnings Plugin"
    assert plugin.PLUGIN_NAME == "lightnings_fmi"
    assert plugin.plugin_name == "lightnings_fmi"

    # Check default value in config fields
    history_field = next(f for f in metadata["config_fields"] if f.name == "history")
    assert history_field.default_value == 300


def test_argb_color() -> None:
    """Test ARGB color calculation"""
    plugin = FMILightningsPlugin({})

    # Fresh strike
    assert plugin._get_argb_color(0) == "-1"
    assert plugin._get_argb_color(299) == "-1"

    # 5-15 mins
    assert plugin._get_argb_color(300) == "-256"
    assert plugin._get_argb_color(899) == "-256"

    # 15-30 mins
    assert plugin._get_argb_color(900) == "-35072"
    assert plugin._get_argb_color(1799) == "-35072"

    # 30-45 mins
    assert plugin._get_argb_color(1800) == "-65535"
    assert plugin._get_argb_color(2699) == "-65535"

    # > 45 mins
    assert plugin._get_argb_color(2700) == "-7864320"
    assert plugin._get_argb_color(3600) == "-7864320"
