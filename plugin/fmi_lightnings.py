# fmi_lightnings.py from https://github.com/sgofferj/trakbridge-plugin-lightnings-fmi.git
#
# Copyright Stefan Gofferje
#
# Licensed under the Gnu General Public License Version 3 or higher (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at https://www.gnu.org/licenses/gpl-3.0.en.html

"""
Finnish Meteorological Institute Lightning Plugin for TrakBridge
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

import aiohttp

# pylint: disable=import-error
from plugins.base_plugin import (
    BaseGPSPlugin,
    PluginConfigField,
)
from services.logging_service import get_module_logger

# pylint: enable=import-error

# Initialize module logger
logger = get_module_logger(__name__)


class FMILightningsPlugin(BaseGPSPlugin):
    """FMI Lightning integration"""

    PLUGIN_NAME = "lightnings_fmi"
    WFS_BASE_URL = (
        "https://opendata.fmi.fi/wfs?service=WFS&version=2.0.0&request=getFeature"
        "&storedquery_id=fmi::observations::lightning::multipointcoverage"
    )

    # Namespaces for XML parsing
    NS = {
        "gml": "http://www.opengis.net/gml/3.2",
        "gmlcov": "http://www.opengis.net/gmlcov/1.0",
        "swe": "http://www.opengis.net/swe/2.0",
        "om": "http://www.opengis.net/om/2.0",
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._last_fetch_time: datetime = datetime.now(timezone.utc)

    @classmethod
    def get_plugin_name(cls) -> str:
        return cls.PLUGIN_NAME

    @property
    def plugin_name(self) -> str:
        return self.PLUGIN_NAME

    @property
    def plugin_metadata(self) -> Dict[str, Any]:
        return {
            "display_name": "FMI Lightnings Plugin",
            "description": ("Get lightning strike data from Finnish Meteorological Institute"),
            "icon": "fas fa-bolt",
            "category": "custom",
            "min_poll_interval": 30,
            "hide_cot_type": True,
            "config_fields": [
                PluginConfigField(
                    name="history",
                    label="History (seconds)",
                    field_type="number",
                    required=False,
                    default_value=300,
                    help_text="How many seconds back to fetch lightnings",
                    min_value=30,
                    max_value=3600,
                ),
            ],
            "help_sections": [
                {
                    "title": "Overview",
                    "content": [
                        "This plugin pulls lightning strike data from "
                        "the FMI open data service.",
                        "It displays strikes as map markers with thunderstorm icons.",
                        "Strikes are colored based on their age to indicate freshness.",
                    ],
                }
            ],
        }

    def _get_argb_color(self, age_seconds: float) -> str:
        """Get ARGB color based on strike age."""
        if age_seconds >= 2700:
            return "-7864320"
        if age_seconds >= 1800:
            return "-65535"
        if age_seconds >= 900:
            return "-35072"
        if age_seconds >= 300:
            return "-256"
        return "-1"

    async def _fetch_fmi_data(
        self, session: aiohttp.ClientSession, start_time: datetime, end_time: datetime
    ) -> bytes:
        """Fetch raw XML data from FMI WFS."""
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{self.WFS_BASE_URL}&starttime={start_time_str}&endtime={end_time_str}"

        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"FMI: Failed to fetch data: HTTP {response.status}")
                return b""
            return await response.read()

    def _parse_lightning_xml(self, xml_content: bytes) -> List[Dict[str, Any]]:
        """Parse lightning XML data."""
        if not xml_content:
            return []

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            logger.error(f"FMI: Failed to parse XML: {e}")
            return []

        # Use the timestamp from the XML response as 'now' to avoid clock skew issues
        now_str = root.get("timeStamp")
        if now_str:
            try:
                # fromisoformat with Z support is 3.11+, so use strptime for 3.10
                now = datetime.strptime(now_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except ValueError:
                now = datetime.now(timezone.utc)
        else:
            now = datetime.now(timezone.utc)

        # Find positions
        pos_elem = root.find(".//gmlcov:positions", self.NS)
        if pos_elem is None or not pos_elem.text:
            logger.info("FMI: No lightning strikes found in this interval")
            return []

        positions = [float(x) for x in pos_elem.text.split()]
        lats = positions[::3]
        lons = positions[1::3]
        times = positions[2::3]

        # Find data tuples (multiplicity, peak_current, cloud_indicator, ellipse_major)
        tuple_elem = root.find(".//gml:doubleOrNilReasonTupleList", self.NS)
        if tuple_elem is None or not tuple_elem.text:
            return []

        data_rows = tuple_elem.text.strip().split("\n")
        data = [[float(x) for x in row.split()] for row in data_rows]

        # Find field names to know where ellipse_major is
        fields = root.findall(".//swe:field", self.NS)
        field_names = [f.attrib["name"] for f in fields]
        try:
            em_idx = field_names.index("ellipse_major")
        except ValueError:
            em_idx = -1

        locations = []

        for i, lat in enumerate(lats):
            strike_time = datetime.fromtimestamp(times[i], tz=timezone.utc)
            lon = lons[i]

            uid = f"lightning-{strike_time.strftime('%Y%m%dT%H%M%SZ')}-" f"{lon}-{lat}"

            age_seconds = (now - strike_time).total_seconds()
            argb = self._get_argb_color(age_seconds)

            # Accuracy (Horizontal Error) in meters
            he = 100.0
            if em_idx != -1 and i < len(data):
                he = data[i][em_idx] * 1000

            remarks = (
                f"Strike time: {strike_time.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
                "Säähavainnot: Ilmatieteenlaitos avoin data, CC-BY 4.0\n"
                "Weather observations: "
                "Finnish Meteorological Institute open data, CC-BY 4.0\n"
                "#weather #lightning"
            )

            locations.append(
                {
                    "uid": uid,
                    "name": "Lightning strike",
                    "lat": lat,
                    "lon": lon,
                    "hae": 5000,
                    "ce": he,
                    "le": 10,
                    "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    "description": remarks,
                    "cot_type": "a-o-G",
                    "custom_cot_attrib": {
                        "detail": {
                            "usericon": {
                                "_attributes": {
                                    "iconsetpath": (
                                        "ad78aafb-83a6-4c07-b2b9-a897a8b6a38f/"
                                        "Shapes/thunderstorm.png"
                                    )
                                }
                            },
                            "color": {"_attributes": {"argb": argb}},
                        }
                    },
                }
            )

        return locations

    async def fetch_locations(self, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """Fetch lightning strikes from FMI."""
        config = self.get_decrypted_config()
        history = int(config.get("history", 300))

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(seconds=history)

        xml_content = await self._fetch_fmi_data(session, start_time, end_time)
        # XML parsing is CPU bound, but for small lightning data it should be fine.
        # Running in thread if it becomes an issue.
        locations = self._parse_lightning_xml(xml_content)

        logger.info(f"FMI: Fetched {len(locations)} lightning strikes")
        return locations

    def validate_config(self) -> bool:
        """Validate configuration."""
        # History is optional with default value
        return True

    async def test_connection(self) -> Dict[str, Any]:
        """Test connection by fetching recent lightnings."""
        try:
            async with aiohttp.ClientSession() as session:
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(minutes=5)
                xml_content = await self._fetch_fmi_data(session, start_time, end_time)
                if xml_content:
                    return {"success": True, "message": "Successfully connected to FMI WFS"}
                return {"success": False, "message": "Received empty response from FMI"}
        except Exception as e:  # pylint: disable=broad-exception-caught
            return {"success": False, "message": f"Connection failed: {e}"}
