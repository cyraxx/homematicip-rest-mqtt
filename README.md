# Homematic IP REST API to MQTT bridge

Bridges between Homematic IP components using the REST API (i.e. using an Homematic IP Access Point, not a CCU)
and an MQTT broker so you can use your home automation software of choice to interact with Homematic IP.

# ⚠️ Work in progress

I'm still working on this. In its current state, it offers Homematic IP to MQTT functionality but not the other
way around. In other words, you can't control your devices through MQTT but only receive their current state.

# Instructions

Install the module requirements using `pip install -r requirements.txt`.

Before first use, you need to follow the instructions for
[homematicip-rest-api](https://github.com/hahn-th/homematicip-rest-api#usage) to generate the config file
containing your auth token.

Then simply run `main.py --server <ip of your MQTT server>`, add `--debug` if you want to see what's going on.

To run as a daemon using systemd, see `homematicip-rest-mqtt.service` for a starting point.

# Supported devices

Currently only a handful of devices are supported, simply because these are the ones I happened to need.
Additional devices are pretty trivial to implement though.

## Heating group (aka room)

MQTT topics:
- `homematicip/groups/heating/<group_id>/label`: Group (room) name
- `homematicip/groups/heating/<group_id>/set`: Set point temperature
- `homematicip/groups/heating/<group_id>/temperature`: Current temperature
- `homematicip/groups/heating/<group_id>/humidity`: Current humidity
- `homematicip/groups/heating/<group_id>/valve`: Current valve position (0..1)
- `homematicip/groups/heating/<group_id>/window`: Current window state (`OPEN`,`CLOSED`,`TILTED`)
- `homematicip/groups/heating/<group_id>/mode`: Current control mode (`AUTOMATIC`, `MANUAL`, `ECO`)

## Heating thermostat (valve)

Homematic IP product codes: HMIP-eTRV, HMIP-eTRV-C

MQTT topics:
- `homematicip/devices/thermostat/<device_id>/low_battery`: Low battery state
- `homematicip/devices/thermostat/<device_id>/set`: Set point temperature
- `homematicip/devices/thermostat/<device_id>/temperature`: Current temperature
- `homematicip/devices/thermostat/<device_id>/valve`: Current valve position (0..1)

## Wall mounted thermostat

Homematic IP product codes: HMIP-WTH, HMIP-WTH-2, HMIP-BWTH

MQTT topics:
- `homematicip/devices/wall_thermostat/<device_id>/low_battery`: Low battery state
- `homematicip/devices/wall_thermostat/<device_id>/set`: Set point temperature
- `homematicip/devices/wall_thermostat/<device_id>/temperature`: Current temperature
- `homematicip/devices/wall_thermostat/<device_id>/humidity`: Current humidity

## Window/contact sensor

Homematic IP product codes: HMIP-SWDO, HMIP-SWDO-I, HMIP-SWDM, HMIP-SWDM-B2, HMIP-SCI, HMIP-SRH

MQTT topics:
- `homematicip/devices/window/<device_id>/low_battery`: Low battery state
- `homematicip/devices/window/<device_id>/state`: Current window state (`OPEN`,`CLOSED`,`TILTED`)
