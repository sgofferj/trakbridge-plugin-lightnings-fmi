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

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

import aiohttp
from fmiopendata.wfs import download_stored_query

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

    # pylint: disable=unused-argument
    async def fetch_locations(self, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """Fetch lightning strikes from FMI."""
        # pylint: disable=too-many-locals
        config = self.get_decrypted_config()
        history = int(config.get("history", 300))

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(seconds=history)

        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            # download_stored_query is synchronous, run in thread
            obs = await asyncio.to_thread(
                download_stored_query,
                "fmi::observations::lightning::multipointcoverage",
                args=[f"starttime={start_time_str}", f"endtime={end_time_str}"],
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"FMI: Failed to fetch lightning data: {e}")
            return []

        locations = []
        now = datetime.now(timezone.utc)

        for i, lat in enumerate(obs.latitudes):
            strike_time = obs.times[i].replace(tzinfo=timezone.utc)
            lon = obs.longitudes[i]

            uid = f"lightning-{strike_time.strftime('%Y%m%dT%H%M%SZ')}-" f"{lon}-{lat}"

            age_seconds = (now - strike_time).total_seconds()
            argb = self._get_argb_color(age_seconds)

            # Accuracy (Horizontal Error) in meters
            he = obs.ellipse_major[i] * 1000 if obs.ellipse_major[i] else 100

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
                    "hae": 5000,  # Default HAE from original feeder
                    "ce": he,
                    "le": 10,
                    "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    "description": remarks,
                    "cot_type": "a-o-G",  # Ground Combat (as in original)
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

        logger.info(f"FMI: Fetched {len(locations)} lightning strikes")
        return locations

    def validate_config(self) -> bool:
        """Validate configuration."""
        # History is optional with default value
        return True

    async def test_connection(self) -> Dict[str, Any]:
        """Test connection by fetching recent lightnings."""
        try:
            # Use a short history for testing
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=5)
            start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            await asyncio.to_thread(
                download_stored_query,
                "fmi::observations::lightning::multipointcoverage",
                args=[f"starttime={start_time_str}", f"endtime={end_time_str}"],
            )
            return {"success": True, "message": "Successfully connected to FMI WFS"}
        except Exception as e:  # pylint: disable=broad-exception-caught
            return {"success": False, "message": f"Connection failed: {e}"}
