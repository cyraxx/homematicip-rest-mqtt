#!/usr/bin/env python3
import argparse
import logging
import random

import paho.mqtt.client as mqtt

import homematicip
from homematicip.home import Home
from homematicip.device import HeatingThermostat, HeatingThermostatCompact, ShutterContact, ShutterContactMagnetic, ContactInterface, RotaryHandleSensor, WallMountedThermostatPro, WeatherSensor
from homematicip.group import HeatingGroup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

parser = argparse.ArgumentParser()
parser.add_argument('--server', required=True, help="Address of the MQTT server")
parser.add_argument('--port', type=int, default=1883, help="Port of the MQTT server")
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
        logger.error("No configuration file found. Run hmip_generate_auth_token.py and copy config.ini to a suitable location.")
        return

    home.set_auth_token(config.auth_token)
    home.init(config.access_point)

    home.get_current_state()

    client.on_connect = onMQTTConnect
    client.on_message = onMQTTMessage
    try:
        client.connect(args.server, args.port)
    except Exception as err:
        logger.error("Error connecting to MQTT server: %s", err)
        return

    try:
        while True:
            client.loop()
    except KeyboardInterrupt:
        return

def onMQTTConnect(client, userdata, flags, rc):
    logger.info("MQTT connection status: %s", mqtt.connack_string(rc))

    # subscribe to all set-Topics
    client.subscribe("cmd/homematicip/devices/+/+/+")

    logger.debug("Performing initial group sync")
    for group in home.groups:
        updateHomematicObject(group)

    logger.debug("Performing initial device sync")
    for device in home.devices:
        updateHomematicObject(device)

    home.onEvent += onHomematicEvents
    home.onWsError += onWebsocketError
    home.websocket_reconnect_on_error = False
    home.enable_events()

    logger.info("Running")

def onMQTTMessage(client, userdata, msg):
    # process received command
    logger.debug("Message received-> " + msg.topic + " " + str(msg.payload))

    # TODO: parse topic
    deviceId = "11b9746f-7891-4592-8ac9-a8a5e3cd24fc"

    try:
        # check if update applicable (eg. wrong item, wrong property)
        #device = home.search_device_by_id(deviceId)
        device =  home.search_group_by_id(deviceId)

        deviceType = type(device)
        print(deviceType)

        if deviceType == HeatingGroup:
            device.set_point_temperature(13)
        else:
            logger.warning("No updates allowed on device of type " + str(deviceType))
            return

        #device.is_update_applicable()
        device.authorizeUpdate()
    except Exception as ex:
        logger.error("Processing received command failed: " + str(ex))

def onWebsocketError(err):
    logger.error("Websocket disconnected, trying to reconnect: %s", err)
    home.disable_events()
    home.enable_events()

def onHomematicEvents(eventList):
    for event in eventList:
        eventType = event["eventType"]
        payload = event["data"]

        logger.debug("Received event of type %s: %s", eventType, payload)
        if not eventType in ("DEVICE_CHANGED", "GROUP_CHANGED"):
            continue

        updateHomematicObject(payload)

def updateHomematicObject(payload):
    payloadType = type(payload)
    topic = "homematicip/"

    if payloadType == HeatingGroup:
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
    elif payloadType in (HeatingThermostat, HeatingThermostatCompact):
        topic += "devices/thermostat/" + payload.id
        data = {
            "low_battery": payload.lowBat,
            "set": payload.setPointTemperature,
            "temperature": payload.valveActualTemperature,
            "valve": payload.valvePosition
        }
    elif payloadType in (ShutterContact, ShutterContactMagnetic, ContactInterface, RotaryHandleSensor):
        topic += "devices/window/" + payload.id
        data = {
            "low_battery": payload.lowBat,
            "state": payload.windowState
        }
    elif payloadType == WallMountedThermostatPro:
        topic += "devices/wall_thermostat/" + payload.id
        data = {
            "low_battery": payload.lowBat,
            "set": payload.setPointTemperature,
            "temperature": payload.actualTemperature,
            "humidity": payload.humidity
        }
    elif payloadType == WeatherSensor:
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
    else:
        return

    for k, v in data.items():
        fullTopic = topic + "/" + k
        logger.debug("Publishing to %s: %s", fullTopic, v)
        if not args.no_publish:
            client.publish(fullTopic, v, qos=0, retain=True)

if __name__ == "__main__":
    main()
