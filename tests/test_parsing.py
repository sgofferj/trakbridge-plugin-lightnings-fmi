# pylint: disable=protected-access
import sys
import types
from unittest.mock import MagicMock
from typing import Dict, Any

# Mock trakbridge imports
mock_base_plugin = types.ModuleType("plugins.base_plugin")
mock_logging_service = types.ModuleType("services.logging_service")


# Define mock classes/functions needed for import
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


mock_base_plugin.BaseGPSPlugin = MockBaseGPSPlugin  # type: ignore
mock_base_plugin.PluginConfigField = MockPluginConfigField  # type: ignore
mock_logging_service.get_module_logger = MagicMock()  # type: ignore

sys.modules["plugins.base_plugin"] = mock_base_plugin
sys.modules["services.logging_service"] = mock_logging_service

from plugin.fmi_lightnings import FMILightningsPlugin


def test_parsing_order() -> None:
    """Test that lightning strikes are sorted oldest first."""
    plugin = FMILightningsPlugin({})

    # Mock XML content with 3 strikes out of order
    # strike 1: time=2000 (middle)
    # strike 2: time=1000 (oldest)
    # strike 3: time=3000 (newest)
    # positions format: lat lon time
    xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" 
    xmlns:gml="http://www.opengis.net/gml/3.2" 
    xmlns:gmlcov="http://www.opengis.net/gmlcov/1.0" 
    xmlns:swe="http://www.opengis.net/swe/2.0" 
    timeStamp="2024-05-19T12:00:00Z">
    <gmlcov:positions>
        60.0 24.0 2000
        60.1 24.1 1000
        60.2 24.2 3000
    </gmlcov:positions>
    <gml:doubleOrNilReasonTupleList>
        1.0 10.0 0.0 0.1
        1.0 10.0 0.0 0.1
        1.0 10.0 0.0 0.1
    </gml:doubleOrNilReasonTupleList>
    <swe:field name="multiplicity"/>
    <swe:field name="peak_current"/>
    <swe:field name="cloud_indicator"/>
    <swe:field name="ellipse_major"/>
</wfs:FeatureCollection>
"""

    locations = plugin._parse_lightning_xml(xml_content)

    assert len(locations) == 3

    # If not sorted, they will be in order of XML: 2000, 1000, 3000
    # We want them sorted: 1000, 2000, 3000
    times_in_order = []
    for loc in locations:
        # Extract time from description "Strike time: 1970-01-01T00:33:20Z"
        # 1000 -> 00:16:40
        # 2000 -> 00:33:20
        # 3000 -> 00:50:00
        time_part = loc["description"].split("\n")[0].split(": ")[1]
        times_in_order.append(time_part)

    assert times_in_order[0] < times_in_order[1]
    assert times_in_order[1] < times_in_order[2]


if __name__ == "__main__":
    test_parsing_order()
