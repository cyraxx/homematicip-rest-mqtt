#!/usr/bin/env python3
import argparse
import asyncio
import logging
import random

import aiomqtt

import homematicip
from homematicip.async_home import AsyncHome
from homematicip.device import HeatingThermostat, HeatingThermostatCompact, ShutterContact, ShutterContactMagnetic, \
    ContactInterface, RotaryHandleSensor, WallMountedThermostatPro, TemperatureHumiditySensorWithoutDisplay, WeatherSensor, HoermannDrivesModule, \
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
home = AsyncHome()
mqtt_client = None


async def main():
    global mqtt_client

    config = homematicip.find_and_load_config_file()
    if config is None:
        logger.error("No configuration file found. Run hmip_generate_auth_token.py and copy config.ini to a suitable "
                     "location.")
        return

    await home.init_async(config.access_point, config.auth_token)
    await home.get_current_state_async()

    try:
        async with aiomqtt.Client(
            hostname=args.server,
            port=args.port,
            username=args.username,
            password=args.password,
            identifier=client_id
        ) as client:
            mqtt_client = client

            await setup_mqtt_client(client)
            logger.info("MQTT connected, enabling Homematic events")

            # Set up homematic event handling
            home.onEvent += on_homematic_events
            home.onWsError += on_websocket_error
            home.websocket_reconnect_on_error = False
            await home.enable_events()

            logger.info("Running")

            # Keep the client running
            while True:
                await asyncio.sleep(1)

    except aiomqtt.MqttError as error:
        logger.error(f"Error connecting to MQTT server: {error}")
    except asyncio.exceptions.CancelledError:
        return


async def setup_mqtt_client(mqtt_client):
    # Subscribe to topics
    await mqtt_client.subscribe("cmd/homematicip/groups/heating/+/set")
    await mqtt_client.subscribe("cmd/homematicip/devices/hoermann_drive/+/state")
    await mqtt_client.subscribe("cmd/homematicip/home/alarm/+/state")

    logger.debug("Performing initial group sync")
    for group in home.groups:
        await process_homematic_payload(group)

    logger.debug("Performing initial device sync")
    for device in home.devices:
        await process_homematic_payload(device)

    # Start message handler as a background task
    asyncio.create_task(handle_mqtt_messages(mqtt_client))


async def handle_mqtt_messages(mqtt_client):
    async for message in mqtt_client.messages:
        try:
            logger.info(f"Message received-> {message.topic} {message.payload}")

            value = message.payload.decode("UTF-8")

            # parse topic
            topic_as_array = message.topic.value.split('/')
            device_or_group = topic_as_array[2]
            type_name = topic_as_array[3]
            id_value = topic_as_array[4]

            if device_or_group == "groups":
                await update_homematic_group(id_value, value)
            elif device_or_group == "devices":
                await update_homematic_device(id_value, value)
            elif device_or_group == "home":
                await update_homematic_home(type_name, value)
            else:
                logger.warning(f"Updating {device_or_group} not yet implemented")
        except Exception as e:
            logger.error(f"Error processing message: {e}")


async def update_homematic_group(group_id, value):
    try:
        group = home.search_group_by_id(group_id)
        error = None

        if isinstance(group, HeatingGroup):
            result = await group.set_point_temperature_async(float(value))
            if not result.success:
                error = result.text
        else:
            logger.error(f"No updates allowed on groups of type {type(group)}")

        if error:
            logger.error(f"Updating group {type(group)} failed: {error}")

    except Exception as ex:
        logger.error(f"update_homematic_group failed: {ex}")


async def update_homematic_device(device_id, value):
    try:
        device = home.search_device_by_id(device_id)
        error = None

        if isinstance(device, HoermannDrivesModule):
            if value == "CLOSED":
                door_command = DoorCommand.CLOSE
            elif value == "OPEN":
                door_command = DoorCommand.OPEN
            elif value == "STOP":
                door_command = DoorCommand.STOP
            elif value == "PARTIAL_OPEN":
                door_command = DoorCommand.PARTIAL_OPEN
            else:
                logger.error(f"Invalid command for hoermann drive. Command: {value}")
                return
            result = await device.send_door_command_async(doorCommand=door_command)
            if not result.success:
                error = result.text
        else:
            logger.error(f"No updates allowed on devices of type {type(device)}")

        if error:
            logger.error(f"Updating device {type(device)} failed: {error}")

    except Exception as ex:
        logger.error(f"update_homematic_device failed: {ex}")


async def update_homematic_home(type_name, value):
    try:
        error = None
        if type_name == "alarm":
            if value == 'ABSENCE_MODE':
                internal_active = True
                external_active = True
            elif value == 'PRESENCE_MODE':
                internal_active = False
                external_active = True
            else:
                internal_active = False
                external_active = False

            await home.set_security_zones_activation_async(internal_active, external_active)
        else:
            logger.error(f"No updates allowed on home for type {type_name}")

        if error:
            logger.error(f"Updating home {type_name} failed: {error}")

    except Exception as ex:
        logger.error(f"update_homematic_home failed: {ex}")


async def on_websocket_error(err):
    logger.error(f"Websocket error: {err}")


def on_homematic_events(event_list):
    for event in event_list:
        event_type = event["eventType"]
        payload = event["data"]

        logger.debug(f"Received event of type {event_type}: {payload}")
        if event_type not in ("DEVICE_CHANGED", "GROUP_CHANGED", "HOME_CHANGED"):
            continue

        asyncio.create_task(process_homematic_payload(payload))


async def process_homematic_payload(payload):
    global mqtt_client

    if mqtt_client is None:
        logger.debug(f"No MQTT client available to publish event for {payload}")
        return

    topic = "homematicip/"

    if isinstance(payload, HeatingGroup):
        topic += f"groups/heating/{payload.id}"
        data = {
            "label": payload.label,
            "set": payload.setPointTemperature,
            "temperature": payload.actualTemperature,
            "humidity": payload.humidity,
            "valve": payload.valvePosition,
            "window": payload.windowState,
            "mode": payload.controlMode
        }
    elif isinstance(payload, HeatingThermostat | HeatingThermostatCompact):
        topic += f"devices/thermostat/{payload.id}"
        data = {
            "low_battery": payload.lowBat,
            "set": payload.setPointTemperature,
            "temperature": payload.valveActualTemperature,
            "valve": payload.valvePosition
        }
    elif isinstance(payload, ShutterContact | ShutterContactMagnetic | ContactInterface | RotaryHandleSensor):
        topic += f"devices/window/{payload.id}"
        data = {
            "low_battery": payload.lowBat,
            "state": payload.windowState
        }
    elif isinstance(payload, WallMountedThermostatPro):
        topic += f"devices/wall_thermostat/{payload.id}"
        data = {
            "low_battery": payload.lowBat,
            "set": payload.setPointTemperature,
            "temperature": payload.actualTemperature,
            "humidity": payload.humidity
        }
    elif isinstance(payload, TemperatureHumiditySensorWithoutDisplay):
        topic += f"devices/temperature_humidity_sensor/{payload.id}"
        data = {
            "low_battery": payload.lowBat,
            "temperature": payload.actualTemperature,
            "humidity": payload.humidity,
            "vapor_amount": payload.vaporAmount
        }
    elif isinstance(payload, WeatherSensor):
        topic += f"devices/weather/{payload.id}"
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
    elif isinstance(payload, HoermannDrivesModule):
        topic += f"devices/hoermann_drive/{payload.id}"
        data = {
            "state": payload.doorState
        }
    elif isinstance(payload, MotionDetectorIndoor):
        topic += f"devices/motion_detector/{payload.id}"
        data = {
            "low_battery": payload.lowBat,
            "current_illumination": payload.currentIllumination,
            "illumination": payload.illumination,
            "motion_detected": payload.motionDetected
        }
    elif isinstance(payload, SmokeDetector):
        topic += f"devices/smoke_detector/{payload.id}"
        data = {
            "low_battery": payload.lowBat
        }
    elif isinstance(payload, AlarmSirenIndoor):
        topic += f"devices/alarm_siren/{payload.id}"
        data = {
            "low_battery": payload.lowBat
        }
    elif isinstance(payload, AsyncHome):
        topic += f"home/alarm/{payload.id}"
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
    elif isinstance(payload, LightSensor):
        topic += f"devices/light_sensor/{payload.id}"
        data = {
            "average": payload.averageIllumination,
            "current": payload.currentIllumination,
            "highest": payload.highestIllumination,
            "lowest": payload.lowestIllumination
        }
    else:
        logger.debug(f"Unhandled type: {type(payload)}")
        return

    for k, v in data.items():
        full_topic = f"{topic}/{k}"
        if not args.no_publish:
            try:
                await mqtt_client.publish(full_topic, v, qos=0, retain=True)
                logger.debug(f"Published to {full_topic}: {v}")
            except Exception as ex:
                logger.error(f"Failed to publish to {full_topic}: {ex}")
        else:
            logger.info(f"Would publish to {full_topic}: {v}")



if __name__ == "__main__":
    asyncio.run(main())
