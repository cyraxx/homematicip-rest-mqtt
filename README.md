# Homematic IP REST API to MQTT bridge

Bridges between Homematic IP components using the REST API (i.e. using an Homematic IP Access Point, not a CCU)
and an MQTT broker so you can use your home automation software of choice to interact with Homematic IP.

In its current state, it offers Homematic IP to MQTT functionality for a number of devices (see below) and
MQTT to Homematic IP functionality for a very limited number of devices and values. Additional devices are
pretty trivial to implement so feel free to open a PR.

# Instructions

Install the module requirements using `pip install -r requirements.txt`.

Before first use, you need to follow the instructions for
[homematicip-rest-api](https://github.com/hahn-th/homematicip-rest-api#usage) to generate the config file
containing your auth token.

Then simply run `main.py --server <ip of your MQTT server>`, add `--debug` if you want to see what's going on.

To run as a daemon using systemd, see `homematicip-rest-mqtt.service` for a starting point.

# Supported devices

## Home (alarm state)

Property | MQTT topic (read) | MQTT topic (write)
--- | --- | ---
Current alarm state (`OFF`, `ABSENCE_MODE`, `PRESENCE_MODE`) | `homematicip/home/alarm/<home_id>/state` | `cmd/homematicip/home/alarm/<home_id>/state`

## Heating group (aka room)

Property | MQTT topic (read) | MQTT topic (write)
--- | --- | ---
Group (room) name | `homematicip/groups/heating/<group_id>/label`
Set point temperature | `homematicip/groups/heating/<group_id>/set` | `cmd/homematicip/groups/heating/<group_id>/set`
Current temperature | `homematicip/groups/heating/<group_id>/temperature`
Current humidity | `homematicip/groups/heating/<group_id>/humidity`
Current valve position (0..1) | `homematicip/groups/heating/<group_id>/valve`
Current window state (`OPEN`,`CLOSED`,`TILTED`) | `homematicip/groups/heating/<group_id>/window`
Current control mode (`AUTOMATIC`, `MANUAL`, `ECO`) | `homematicip/groups/heating/<group_id>/mode`

## Heating thermostat (valve)

Homematic IP product codes: HMIP-eTRV, HMIP-eTRV-C

Property | MQTT topic (read) | MQTT topic (write)
--- | --- | ---
Low battery state | `homematicip/devices/thermostat/<device_id>/low_battery`
Set point temperature | `homematicip/devices/thermostat/<device_id>/set`
Current temperature | `homematicip/devices/thermostat/<device_id>/temperature`
Current valve position (0..1) | `homematicip/devices/thermostat/<device_id>/valve`

## Wall mounted thermostat

Homematic IP product codes: HMIP-WTH, HMIP-WTH-2, HMIP-BWTH

Property | MQTT topic (read) | MQTT topic (write)
--- | --- | ---
Low battery state | `homematicip/devices/wall_thermostat/<device_id>/low_battery`
Set point temperature | `homematicip/devices/wall_thermostat/<device_id>/set`
Current temperature | `homematicip/devices/wall_thermostat/<device_id>/temperature`
Current humidity | `homematicip/devices/wall_thermostat/<device_id>/humidity`

## Window/contact sensor

Homematic IP product codes: HMIP-SWDO, HMIP-SWDO-I, HMIP-SWDM, HMIP-SWDM-B2, HMIP-SCI, HMIP-SRH

Property | MQTT topic (read) | MQTT topic (write)
--- | --- | ---
Low battery state | `homematicip/devices/window/<device_id>/low_battery`
Current window state (`OPEN`,`CLOSED`,`TILTED`) | `homematicip/devices/window/<device_id>/state`

## Motion detector indoor

Homematic IP product code: HMIP-SMI

Property | MQTT topic (read) | MQTT topic (write)
--- | --- | ---
Low battery state | `homematicip/devices/motion_detector/<device_id>/low_battery`
Current illumination | `homematicip/devices/motion_dector/<device_id>/current_illumination`
Illumination | `homematicip/devices/motion_detector/<device_id>/illumination`
Motion detected | `homematicip/devices/motion_detector/<device_id>/motion_detected`

## Smoke detector

Homematic IP product code: HMIP-SWSD

Property | MQTT topic (read) | MQTT topic (write)
--- | --- | ---
Low battery state | `homematicip/devices/smoke_detector/<device_id>/low_battery`

## Alarm siren indoor

Homematic IP product code: HMIP-ASIR-2

Property | MQTT topic (read) | MQTT topic (write)
--- | --- | ---
Low battery state | `homematicip/devices/alarm_siren/<device_id>/low_battery`

## Weather sensor (basic)

Homematic IP product code: HmIP-SWO-B

Property | MQTT topic (read) | MQTT topic (write)
--- | --- | ---
Low battery state | `homematicip/devices/weather/<device_id>/low_battery`
Current temperature | `homematicip/devices/weather/<device_id>/temperature`
Current humidity | `homematicip/devices/weather/<device_id>/humidity`
Current illumination | `homematicip/devices/weather/<device_id>/illumination`
Illumination threshold sunshine | `homematicip/devices/weather/<device_id>/illumination_threshold_sunshine`
Storm | `homematicip/devices/weather/<device_id>/storm`
Sunshine | `homematicip/devices/weather/<device_id>/sunshine`
Today sunshine duration | `homematicip/devices/weather/<device_id>/today_sunshine_duration`
Total sunshine duration | `homematicip/devices/weather/<device_id>/total_sunshine_duration`
Wind value type | `homematicip/devices/weather/<device_id>/wind_value_type`
Wind speed | `homematicip/devices/weather/<device_id>/wind_speed`
Yesterday sunshine duration | `homematicip/devices/weather/<device_id>/yesterday_sunshine_duration`
Vapor amount | `homematicip/devices/weather/<device_id>/vapor_amount`

## Hoermann Gate Drive

Homematic IP product code: HmIP-MOD-HO

Property | MQTT topic (read) | MQTT topic (write)
--- | --- | ---
Current door state (`CLOSED`, `OPEN`, `STOP`, `PARTIAL_OPEN`) | `homematicip/devices/hoermann_drive/<device_id>/state` | `cmd/homematicip/devices/hoermann_drive/<device_id>/state`

## Light sensor

Homematic IP product code: HMIP-SLO

MQTT topics:
- `homematicip/devices/light_sensor/current`: Current illumination
- `homematicip/devices/light_sensor/average`: Average illumination
- `homematicip/devices/light_sensor/highest`: Highest illumination
- `homematicip/devices/light_sensor/lowest`: Lowest illumination
