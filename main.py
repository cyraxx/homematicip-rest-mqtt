#!/usr/bin/env python3
import argparse
import logging
import random

import paho.mqtt.client as mqtt

import homematicip
from homematicip.home import Home
from homematicip.device import HeatingThermostat, HeatingThermostatCompact, ShutterContact, ShutterContactMagnetic, \
    ContactInterface, RotaryHandleSensor, WallMountedThermostatPro, WeatherSensor, HoermannDrivesModule, \
    MotionDetectorIndoor, SmokeDetector, AlarmSirenIndoor, LightSensor
from homematicip.group import HeatingGroup
from homematicip.base.enums import DoorCommand

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

parser = argparse.ArgumentParser()
parser.add_argument('--server', required=True, help="Address of the MQTT server")
parser.add_argument('--port', type=int, default=1883, help="Port of the MQTT server")
parser.add_argument('--username', help="Username for the MQTT server")
parser.add_argument('--password', help="Password for the MQTT server")
parser.add_argument('--debug', action="store_true", help="Enable debug logging")
parser.add_argument('--no-publish', action="store_true", help="Don't actually publish messages (log only)")
args = parser.parse_args()

if args.debug:
    logger.setLevel(logging.DEBUG)

client_id = f'homematicip-mqtt-{random.randint(0, 1000)}'
client = mqtt.Client(client_id)
home = Home()


def main():
    config = homematicip.find_and_load_config_file()
    if config is None:
        logger.error("No configuration file found. Run hmip_generate_auth_token.py and copy config.ini to a suitable "
                     "location.")
        return

    home.set_auth_token(config.auth_token)
    home.init(config.access_point)

    home.get_current_state()

    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message
    try:
        client.username_pw_set(args.username, args.password)
        client.connect(args.server, args.port)
    except Exception as err:
        logger.error("Error connecting to MQTT server: %s", err)
        return

    try:
        while True:
            client.loop()
    except KeyboardInterrupt:
        return


def on_mqtt_connect(mqtt_client, userdata, flags, rc):
    logger.info("MQTT connection status: %s", mqtt.connack_string(rc))

    # subscribe to topic for changing the temperature for a heating group
    mqtt_client.subscribe("cmd/homematicip/groups/heating/+/set")

    # subscribe to topic for opening hoermann gate
    mqtt_client.subscribe("cmd/homematicip/devices/hoermann_drive/+/state")

    # subscribe to topic for changing alarm status
    mqtt_client.subscribe("cmd/homematicip/home/alarm/+/state")

    logger.debug("Performing initial group sync")
    for group in home.groups:
        update_homematic_object(group)

    logger.debug("Performing initial device sync")
    for device in home.devices:
        update_homematic_object(device)

    home.onEvent += on_homematic_events
    home.onWsError += on_websocket_error
    home.websocket_reconnect_on_error = False
    home.enable_events()

    logger.info("Running")


def on_mqtt_message(mqtt_client, userdata, msg):
    logger.info("Message received-> " + msg.topic + " " + str(msg.payload))

    value = msg.payload.decode("UTF-8")

    # parse topic
    topic_as_array = msg.topic.split('/')
    device_or_group = topic_as_array[2]
    type = topic_as_array[3]
    id = topic_as_array[4]

    if device_or_group == "groups":
        update_homematic_group(id, value)
    elif device_or_group == "devices":
        update_homematic_device(id, value)
    elif device_or_group == "home":
        update_homematic_home(type, value)
    else:
        logger.warning("Updating " + device_or_group + " not yet implemented")


def update_homematic_group(group_id, value):
    try:
        group = home.search_group_by_id(group_id)
        group_type = type(group)
        error_code = ''
        if group_type == HeatingGroup:
            result = group.set_point_temperature(value)
            error_code = result["errorCode"]
        else:
            logger.error("No updates allowed on groups of type " + str(group_type))

        if error_code:
            logger.error("Updating " + str(group_type) + " failed with code: " + error_code)

    except Exception as ex:
        logger.error("updateHomematicGroup failed: " + str(ex))


def update_homematic_device(device_id, value):
    try:
        device = home.search_device_by_id(device_id)
        device_type = type(device)
        error_code = ''
        if device_type == HoermannDrivesModule:
            if value == "CLOSED":
                door_command = DoorCommand.CLOSE
            elif value == "OPEN":
                door_command = DoorCommand.OPEN
            elif value == "STOP":
                door_command = DoorCommand.STOP
            elif value == "PARTIAL_OPEN":
                door_command = DoorCommand.PARTIAL_OPEN
            else:
                logger.error("Invalid command for hoermann drive. Command: " + value)
                return
            result = device.send_door_command(doorCommand=door_command)
            error_code = result["errorCode"]
        else:
            logger.error("No updates allowed on devices of type " + str(device_type))

        if error_code:
            logger.error("Updating " + str(device_type) + " failed with code: " + error_code)

    except Exception as ex:
        logger.error("updateHomematicDevice failed: " + str(ex))


def update_homematic_home(type, value):
    try:
        error_code = ''
        if type == "alarm":
            if value == 'ABSENCE_MODE':
                internal_active = True
                external_active = True
            elif value == 'PRESENCE_MODE':
                internal_active = False
                external_active = True
            else:
                internal_active = False
                external_active = False

            home.set_security_zones_activation(internal_active, external_active)
        else:
            logger.error("No updates allowed on home for type " + str(type))

        if error_code:
            logger.error("Updating " + str(type) + " failed with code: " + error_code)

    except Exception as ex:
        logger.error("updateHomematicHome failed: " + str(ex))


def on_websocket_error(err):
    logger.error("Websocket disconnected, trying to reconnect: %s", err)
    home.disable_events()
    home.enable_events()


def on_homematic_events(event_list):
    for event in event_list:
        event_type = event["eventType"]
        payload = event["data"]

        logger.debug("Received event of type %s: %s", event_type, payload)
        if event_type not in ("DEVICE_CHANGED", "GROUP_CHANGED", "HOME_CHANGED"):
            continue

        update_homematic_object(payload)


def update_homematic_object(payload):
    payload_type = type(payload)
    topic = "homematicip/"

    if payload_type == HeatingGroup:
        topic += "groups/heating/" + payload.id
        data = {
            "label": payload.label,
            "set": payload.setPointTemperature,
            "temperature": payload.actualTemperature,
            "humidity": payload.humidity,
            "valve": payload.valvePosition,
            "window": payload.windowState,
            "mode": payload.controlMode
        }
    elif payload_type in (HeatingThermostat, HeatingThermostatCompact):
        topic += "devices/thermostat/" + payload.id
        data = {
            "low_battery": payload.lowBat,
            "set": payload.setPointTemperature,
            "temperature": payload.valveActualTemperature,
            "valve": payload.valvePosition
        }
    elif payload_type in (ShutterContact, ShutterContactMagnetic, ContactInterface, RotaryHandleSensor):
        topic += "devices/window/" + payload.id
        data = {
            "low_battery": payload.lowBat,
            "state": payload.windowState
        }
    elif payload_type == WallMountedThermostatPro:
        topic += "devices/wall_thermostat/" + payload.id
        data = {
            "low_battery": payload.lowBat,
            "set": payload.setPointTemperature,
            "temperature": payload.actualTemperature,
            "humidity": payload.humidity
        }
    elif payload_type == WeatherSensor:
        topic += "devices/weather/" + payload.id
        data = {
            "low_battery": payload.lowBat,
            "temperature": payload.actualTemperature,
            "humidity": payload.humidity,
            "illumination": payload.illumination,
            "illumination_threshold_sunshine": payload.illuminationThresholdSunshine,
            "storm": payload.storm,
            "sunshine": payload.sunshine,
            "today_sunshine_duration": payload.todaySunshineDuration,
            "total_sunshine_duration": payload.totalSunshineDuration,
            "wind_value_type": payload.windValueType,
            "wind_speed": payload.windSpeed,
            "yesterday_sunshine_duration": payload.yesterdaySunshineDuration,
            "vapor_amount": payload.vaporAmount
        }
    elif payload_type == HoermannDrivesModule:
        topic += "devices/hoermann_drive/" + payload.id
        data = {
            "state": payload.doorState
        }
    elif payload_type == MotionDetectorIndoor:
        topic += "devices/motion_detector/" + payload.id
        data = {
            "low_battery": payload.lowBat,
            "current_illumination": payload.currentIllumination,
            "illumination": payload.illumination,
            "motion_detected": payload.motionDetected
        }
    elif payload_type == SmokeDetector:
        topic += "devices/smoke_detector/" + payload.id
        data = {
            "low_battery": payload.lowBat
        }
    elif payload_type == AlarmSirenIndoor:
        topic += "devices/alarm_siren/" + payload.id
        data = {
            "low_battery": payload.lowBat
        }
    elif payload_type == Home:
        topic += "home/alarm/" + payload.id
        internal_active, external_active = payload.get_security_zones_activation()
        if internal_active and external_active:
            activation_status = 'ABSENCE_MODE'
        elif external_active and not internal_active:
            activation_status = 'PRESENCE_MODE'
        else:
            activation_status = 'OFF'
        data = {
            "state": activation_status
        }
    elif payload_type == LightSensor:
        topic += "devices/light_sensor/" + payload.id
        data = {
            "average": payload.averageIllumination,
            "current": payload.currentIllumination,
            "highest": payload.highestIllumination,
            "lowest": payload.lowestIllumination
        }
    else:
        logger.debug("Unhandled type: " + str(payload_type))
        return

    for k, v in data.items():
        full_topic = topic + "/" + k
        logger.debug("Publishing to %s: %s", full_topic, v)
        if not args.no_publish:
            client.publish(full_topic, v, qos=0, retain=True)


if __name__ == "__main__":
    main()
