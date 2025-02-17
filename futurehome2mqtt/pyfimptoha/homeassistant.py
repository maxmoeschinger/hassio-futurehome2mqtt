import time

import pyfimptoha.sensor as sensor
import pyfimptoha.meter_elec as meter_elec
import pyfimptoha.chargepoint as chargepoint
import pyfimptoha.light as light
import pyfimptoha.lock as lock
import pyfimptoha.appliance as appliance
import pyfimptoha.thermostat as thermostat
import pyfimptoha.shortcut as shortcut_button
import pyfimptoha.mode as mode_select
from pyfimptoha.helpers.MqttDevice import MqttDevice
from pyfimptoha.mqtt_client import MqttClient

SUPPORTED_SENSORS = ["battery", "sensor_lumin", "sensor_presence", "sensor_temp", "sensor_humid", "sensor_contact"]


def create_components(
        devices: list,
        rooms: list,
        shortcuts: list,
        mode: str,
        mqtt: MqttClient,
        selected_devices_mode: str,
        selected_devices: list,
        debug: bool
):
    """
    Creates HA components out of FIMP devices
    by pushing them to Home Assistant using MQTT discovery
    """

    print('Received list of devices from FIMP. FIMP reported %s devices' % (len(devices)))
    print('Devices without rooms will be ignored')

    get_reports_list = []
    statuses = []

    for device in devices:
        # Skip device without room
        room_id = device["room"]
        if room_id is None:
            continue

        mqtt_device = MqttDevice(
            device_data=device,
            room_alias=get_room_alias(rooms, room_id)
        )
        address = device["fimp"]["address"]
        adapter = mqtt_device.adapter
        name = device["client"]["name"]
        vinc_id = device["id"]
        functionality = device["functionality"]

        # When debugging you have the option to (only) include or exclude (some) devices
        # depending on 'selected_devices_mode'.
        # Format is '<adapter_<address>', to not have conflicting addresses on different adapters
        if selected_devices_mode != "default":
            if selected_devices_mode == "include" and selected_devices and f"{adapter}_{address}" not in selected_devices:
                if debug:
                    print(f"Skipping: {adapter} {address} {name}")
                continue
            elif selected_devices_mode == "exclude" and f"{adapter}_{address}" in selected_devices:
                if debug:
                    print(f"Skipping: {adapter} {address} {name} has been configured to be excluded")
                continue

        if debug:
            print(f"Creating: {adapter} {address} {name}")
            print(f"- Functionality: {functionality}")

        device_services = device["services"].keys()
        for service_name, service in device["services"].items():
            status = None

            # Reusable
            identifier = f"fh_{vinc_id}_{adapter}_{address}_{service_name}"
            state_topic = f"pt:j1/mt:evt{service['addr']}"
            command_topic = f"pt:j1/mt:cmd{service['addr']}"
            model = device["model"] if device.get("model") and device["model"] else ""
            model_alias = device["modelAlias"] if device.get("modelAlias") and device["modelAlias"] else model
            default_component = {
                "name": None,
                "object_id": identifier,
                "unique_id": identifier,
                "device": {
                    "identifiers": f"{adapter}_{address}",
                    "name": f"{name}",
                    "suggested_area": f"{mqtt_device.room_alias}",
                    "hw_version": f"{model}",
                    "model": f"{model_alias}",
                    "sw_version": f"{adapter}_{address}"
                },
                "state_topic": state_topic
            }
            common_params = {
                "mqtt": mqtt,
                "device": device,
                "state_topic": state_topic,
                "identifier": identifier,
                "default_component": default_component
            }


            # Sensors
            # todo add more sensors: alarm_power?, sensor_power. see old sensor.py
            if service_name in SUPPORTED_SENSORS:
                if debug:
                    print(f"- Service: {service_name}")
                status = sensor.new_sensor(**common_params, service_name=service_name)
                if status:
                    statuses.append(status)

            # Meter_elec
            elif service_name == "meter_elec":
                if debug:
                    print(f"- Service: {service_name}")
                status = meter_elec.new_sensor(**common_params, service_name=service_name)
                if status:
                    for s in status:
                        statuses.append((s[0], s[1]))

            # Door lock
            elif service_name == "door_lock":
                if debug:
                    print(f"- Service: {service_name}")
                status = lock.door_lock(**common_params, command_topic=command_topic)
                if status:
                    statuses.append(status)

            # Appliance
            elif functionality == "appliance" or device["type"]["type"] == "boiler":
                if service_name == "out_bin_switch":
                    if debug:
                        print(f"- Service: {service_name}")
                    status = appliance.new_switch(**common_params, command_topic=command_topic)
                if status:
                    statuses.append(status)

            # Thermostat
            elif service_name == "thermostat":
                if debug:
                    print(f"- Service: {service_name}")
                status = thermostat.new_thermostat(**common_params, command_topic=command_topic, devices=devices)
                if status:
                    for s in status:
                        statuses.append((s[0], s[1]))

        if mqtt_device.has_service("chargepoint"):
            if debug:
                print("- Service: chargepoint")

            get_reports_list.extend(
                chargepoint.chargepoint(mqtt, mqtt_device)
            )

        if mqtt_device.functionality == "lighting":
            if debug:
                print("- Service: lightning")
            get_reports_list.extend(
                light.new_light_v2(mqtt, mqtt_device)
            )

    print(f"Publishing {len(get_reports_list)} get_report requests")
    for topic, service, report_name in get_reports_list:
        mqtt.publish_dict(topic, {
            "serv": service,
            "src": "homeassistant",
            "type": report_name,
            "val_t": "null",
            "val": None,
        })
    print(f"Done publishing get_report requests")

    # Mode select (home, away, sleep, vacation)
    status = None
    print('Creating mode select (dropdown). FIMP reported %s mode' % (mode))
    status = mode_select.create(mqtt, mode)
    if status:
        statuses.append(status)


    # Shortcuts (displayed as buttons)
    print('Creating button devices for shortcuts. FIMP reported %s shortcuts' % (len(shortcuts)))
    for shortcut in shortcuts:
        shortcut_button.new_button(mqtt, shortcut, debug)


    time.sleep(2)
    print("Publishing statuses...")
    for state in statuses:
        topic = state[0]
        payload = state[1]
        mqtt.publish(topic, payload)
        if debug:
            print(topic)
    print("Finished pushing statuses...")

def get_room_alias(rooms, room_id):
    room_alias = [room["alias"] for room in rooms if room["id"] == room_id][0]
    return room_alias
