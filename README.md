# FMI Lightnings Plugin for TrakBridge

## Description
This plugin integrates lightning strike data from the Finnish Meteorological Institute's (FMI) open data service into TrakBridge. It provides real-time lightning strike tracking with CoT (Cursor-on-Target) output for TAK, featuring age-based coloring and thunderstorm icons.

## Configuration

| Field | Description | Default |
|-------|-------------|---------|
| history | How many seconds back to fetch lightnings (30-3600) | `300` |

## Features
- Fetches lightning data from FMI WFS service.
- Displays strikes with thunderstorm icons.
- Age-based coloring (fresh = white, 5-15m = yellow, 15-30m = orange, 30-45m = red, >45m = dark red).
- Automatic UID generation based on strike time and location.
- Includes Finnish/English attribution in remarks.

## Container use
Example environment variables for TrakBridge:
```
PLUGIN_LIGHTNINGS_FMI_ENABLED=true
PLUGIN_LIGHTNINGS_FMI_HISTORY=300
```

## Copyright and License
Copyright Stefan Gofferje
Licensed under the Gnu General Public License Version 3 or higher.
