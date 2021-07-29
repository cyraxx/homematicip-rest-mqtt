#!/usr/bin/env python3
import argparse
import json
import logging
import time
import websocket

import paho.mqtt.client as mqtt

import homematicip
from homematicip.home import Home
from homematicip.device import HeatingThermostat, HeatingThermostatCompact, ShutterContact, ShutterContactMagnetic, ContactInterface, RotaryHandleSensor, WallMountedThermostatPro
from homematicip.group import HeatingGroup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

parser = argparse.ArgumentParser()
parser.add_argument('--server', required=True, help="Address of the MQTT server")
parser.add_argument('--port', type=int, default=1883, help="Port of the MQTT server")
parser.add_argument('--debug', action="store_true", help="Enable debug logging")
args = parser.parse_args()

if args.debug:
    logger.setLevel(logging.DEBUG)

client = mqtt.Client()
home = Home()

def main():
    client.on_connect = onMQTTConnect
    try:
        client.connect(args.server, args.port)
    except Exception as err:
        logger.error("Error connecting to MQTT server: %s", err)
        return

    config = homematicip.find_and_load_config_file()
    if config is None:
        logger.error("No configuration file found. Run hmip_generate_auth_token.py and copy config.ini to a suitable location.")
        return

    home.set_auth_token(config.auth_token)
    home.init(config.access_point)

    home.get_current_state()

    home.onEvent += onHomematicEvents
    home.enable_events()
    websocket.enableTrace(False) # home.enable_events() turns this on

    logger.info("Running")

    try:
        while True:
            client.loop()
    except KeyboardInterrupt:
        return

def onMQTTConnect(client, userdata, flags, rc):
    logger.info("MQTT connection status: %s", str(rc))

def onHomematicEvents(eventList):
    for event in eventList:
        topic = "homematicip/"

        logger.debug("Received event of type %s: %s", event["eventType"], event["data"])

        if event["eventType"] == "DEVICE_CHANGED":
            device = event["data"]

            if type(device) in (HeatingThermostat, HeatingThermostatCompact):
                topic += "devices/thermostat/" + device.id
                data = {
                    "low_battery": device.lowBat,
                    "set": device.setPointTemperature,
                    "temperature": device.valveActualTemperature,
                    "valve": device.valvePosition
                }
            elif type(device) in (ShutterContact, ShutterContactMagnetic, ContactInterface, RotaryHandleSensor):
                topic += "devices/window/" + device.id
                data = {
                    "low_battery": device.lowBat,
                    "state": device.windowState
                }
            elif type(device) == WallMountedThermostatPro:
                topic += "devices/wall_thermostat/" + device.id
                data = {
                    "low_battery": device.lowBat,
                    "set": device.setPointTemperature,
                    "temperature": device.actualTemperature,
                    "humidity": device.humidity
                }
            else:
                continue

        elif event["eventType"] == "GROUP_CHANGED":
            group = event["data"]

            if type(group) == HeatingGroup:
                topic += "groups/heating/" + group.id
                data = {
                    "set": group.setPointTemperature,
                    "temperature": group.actualTemperature,
                    "humidity": group.humidity,
                    "valve": group.valvePosition,
                    "window": group.windowState,
                    "mode": group.controlMode
                }
            else:
                continue

        else:
            continue

        for k, v in data.items():
            fullTopic = topic + "/" + k
            logger.debug("Publishing to %s: %s", fullTopic, v)
            client.publish(topic + "/" + k, v, qos=0, retain=True)

if __name__ == "__main__":
    main()
