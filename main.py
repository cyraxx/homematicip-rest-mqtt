#!/usr/bin/env python3
import argparse
import logging
import random

import paho.mqtt.client as mqtt

import homematicip
from homematicip.home import Home
from homematicip.device import HeatingThermostat, HeatingThermostatCompact, ShutterContact, ShutterContactMagnetic, ContactInterface, RotaryHandleSensor, WallMountedThermostatPro, WeatherSensor, HoermannDrivesModule, MotionDetectorIndoor, SmokeDetector, AlarmSirenIndoor
from homematicip.group import HeatingGroup
from homematicip.base.enums import DoorCommand

from pprint import pprint

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

    # subscribe to topic for changing the temperature for a heating group
    client.subscribe("cmd/homematicip/groups/heating/+/set")

    # subscribe to topic for opening hoermann gate
    client.subscribe("cmd/homematicip/devices/hoermanndrive/+/state")

    # subscribe to topic for changing alarm status
    client.subscribe("cmd/homematicip/home/alarm/+/state")

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
    logger.info("Message received-> " + msg.topic + " " + str(msg.payload))

    value = msg.payload.decode("UTF-8")

    # parse topic
    topicAsArray = msg.topic.split('/')
    deviceOrGroup = topicAsArray[2]
    type = topicAsArray[3]
    id = topicAsArray[4]

    if deviceOrGroup == "groups":
        updateHomematicGroup(id, value)
    elif deviceOrGroup == "devices":
        updateHomematicDevice(id, value)
    elif deviceOrGroup == "home":
        updateHomematicHome(type, value)
    else:
        logger.warning("Updating " + deviceOrGroup + " not yet implemented")

def updateHomematicGroup(groupId, value):
    try:
        group =  home.search_group_by_id(groupId)
        groupType = type(group)
        errorCode = ''
        if groupType == HeatingGroup:
            result = group.set_point_temperature(value)
            errorCode = result["errorCode"]
        else:
            logger.error("No updates allowed on groups of type " + str(groupType))

        if errorCode:
            logger.error("Updating " + str(groupType)  + " failed with code: " + errorCode)

    except Exception as ex:
        logger.error("updateHomematicGroup failed: " + str(ex))

def updateHomematicDevice(deviceId, value):
    try:
        device = home.search_device_by_id(deviceId)
        deviceType = type(device)
        errorCode = ''
        if deviceType == HoermannDrivesModule:
            if value == "CLOSED":
                doorCommand = DoorCommand.CLOSE
            elif value == "OPEN":
                doorCommand = DoorCommand.OPEN
            elif value == "STOP":
                doorCommand = DoorCommand.STOP
            elif value == "PARTIAL_OPEN":
                doorCommand = DoorCommand.PARTIAL_OPEN
            else:
                logger.error("Invalid command for hoermann drive. Command: " + value)
                return
            result = device.send_door_command(doorCommand=doorCommand)
            errorCode = result["errorCode"]
        else:
            logger.error("No updates allowed on devices of type " + str(deviceType))

        if errorCode:
            logger.error("Updating " + str(deviceType)  + " failed with code: " + errorCode)

    except Exception as ex:
        logger.error("updateHomematicDevice failed: " + str(ex))

def updateHomematicHome(type, value):
    try:
        errorCode = ''
        if type == "alarm":
            if value == 'ABSENCE_MODE':
                internalActive = True
                externalActive = True
            elif value == 'PRESENCE_MODE':
                internalActive = False
                externalActive = True
            else:
                internalActive = False
                externalActive = False

            home.set_security_zones_activation(internalActive, externalActive)
        else:
            logger.error("No updates allowed on home for type " + str(type))

        if errorCode:
            logger.error("Updating " + str(type)  + " failed with code: " + errorCode)

    except Exception as ex:
        logger.error("updateHomematicHome failed: " + str(ex))

def onWebsocketError(err):
    logger.error("Websocket disconnected, trying to reconnect: %s", err)
    home.disable_events()
    home.enable_events()

def onHomematicEvents(eventList):
    for event in eventList:
        eventType = event["eventType"]
        payload = event["data"]

        logger.debug("Received event of type %s: %s", eventType, payload)
        if not eventType in ("DEVICE_CHANGED", "GROUP_CHANGED", "HOME_CHANGED"):
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
    elif payloadType == HoermannDrivesModule:
        topic += "devices/hoermanndrive/" + payload.id
        data = {
            "state": payload.doorState
        }
    elif payloadType == MotionDetectorIndoor:
        topic += "devices/motiondetector/" + payload.id
        data = {
            "low_battery": payload.lowBat,
            "current_illumination": payload.currentIllumination,
            "illumination": payload.illumination,
            "motion_detected": payload.motionDetected
        }
    elif payloadType == SmokeDetector:
        topic += "devices/smokedetector/" + payload.id
        data = {
            "low_battery": payload.lowBat
        }
    elif payloadType == AlarmSirenIndoor:
        topic += "devices/alarmsiren/" + payload.id
        data = {
            "low_battery": payload.lowBat
        }
    elif payloadType == Home:
        topic += "home/alarm/" + payload.id
        internalActive, externalActive = payload.get_security_zones_activation()
        if internalActive and externalActive:
            activationStatus = 'ABSENCE_MODE'
        elif externalActive and not internalActive:
            activationStatus = 'PRESENCE_MODE'
        else:
            activationStatus = 'OFF'
        data = {
            "state": activationStatus
        }
    else:
        logger.debug("Unhandled type: " + str(payloadType))
        return

    for k, v in data.items():
        fullTopic = topic + "/" + k
        logger.debug("Publishing to %s: %s", fullTopic, v)
        if not args.no_publish:
            client.publish(fullTopic, v, qos=0, retain=True)

if __name__ == "__main__":
    main()
