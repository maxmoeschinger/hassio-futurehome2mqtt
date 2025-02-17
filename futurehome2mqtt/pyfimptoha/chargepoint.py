import json

from pyfimptoha.helpers.MqttDevice import MqttDevice
from pyfimptoha.helpers.MqttDeviceService import MqttDeviceService


def get_max_current(mqtt, chargepoint_service):
    def is_correct(msg, data):
        return "type" in data and data["type"] == "evt.max_current.report"

    d = mqtt.send_and_wait(
        chargepoint_service.command_topic,
        chargepoint_service.state_topic,
        {
            "serv": "chargepoint",
            "src": "homeassistant",
            "type": "cmd.max_current.get_report",
            "val_t": "null",
            "val": None,
        },
        is_correct
    )

    if d is None:
        return None

    msg, data = d
    return data["val"]

def chargepoint(
    mqtt,
    mqtt_device: MqttDevice
):
    chargepoint_service = mqtt_device.get_service("chargepoint")

    if "evt.max_current.report" in chargepoint_service.intf:
        max_current_sensor(mqtt, chargepoint_service)

    max_current = get_max_current(mqtt, chargepoint_service)
    if max_current is None:
        print("Could not determine max_current")
        return

    if "evt.cable_lock.report" in chargepoint_service.intf:
        cable_lock(mqtt, chargepoint_service)
    if "evt.state.report" in chargepoint_service.intf:
        state(mqtt, chargepoint_service)
    if "evt.current_session.report" in chargepoint_service.intf:
        current(mqtt, chargepoint_service, max_current)
    if "cmd.charge.start" in chargepoint_service.intf and "cmd.charge.stop" in chargepoint_service.intf:
        charging(mqtt, chargepoint_service)

    min_current_sensor(mqtt, chargepoint_service)

    return mqtt_device.get_reports_info(["chargepoint"])

def cable_lock(
    mqtt,
    chargepoint_service
):
    local_identifier = chargepoint_service.identifier + "_cable_lock"
    lock_component = {
        "command_topic": chargepoint_service.command_topic,
        "name": "Cable lock",
        "value_template": """
            {% if value_json.type == 'evt.cable_lock.report' %}
                {{ iif(value_json.val, "LOCKED", "UNLOCKED", None) }}
            {% endif %}
        """,
        "payload_lock": """
            {
                "type": "cmd.cable_lock.set",
                "val": true,
                "val_t": "bool",
                "src": "homeassistant"
            }
        """,
        "payload_unlock": """
            {
                "type": "cmd.cable_lock.set",
                "val": false,
                "val_t": "bool",
                "src": "homeassistant"
            }
        """,
        "object_id": local_identifier,
        "unique_id": local_identifier
    }
    merged_component = {**chargepoint_service.get_default_component(), **lock_component}
    payload = json.dumps(merged_component)
    mqtt.publish(f"homeassistant/lock/{local_identifier}/config", payload)


def state(
    mqtt,
    chargepoint_service,
):
    local_identifier = chargepoint_service.identifier + "_state"
    x_component = {
        "name": "State",
        "value_template": """
            {% if value_json.type == 'evt.state.report' %}
                {{ value_json.val }}
            {% else %}
                {{ this.state }}
            {% endif %}
        """,
        "object_id": local_identifier,
        "unique_id": local_identifier
    }
    merged_component = {**chargepoint_service.get_default_component(), **x_component}
    payload = json.dumps(merged_component)
    mqtt.publish(f"homeassistant/sensor/{local_identifier}/config", payload)

def current(
    mqtt,
    chargepoint_service,
    max_current
):
    local_identifier = chargepoint_service.identifier + "_current"
    x_component = {
        "name": "Charge current",
        "command_topic": chargepoint_service.command_topic,
        "value_template": """
            {% if value_json.type == 'evt.current_session.report' and value_json.props.offered_current != '0' %}
                {{ value_json.props.offered_current | int }}
            {% else %}
                {{ this.state }}
            {% endif %}
        """,
        "command_template": """
            {
                "src":"homeassistant",
                "type":"cmd.current_session.set_current",
                "val":{{ value }},
                "val_t": "int",
                "serv": "chargepoint"
            }
        """,
        "unit_of_measurement": "A",
        "min": 0,
        "max": max_current,
        "object_id": local_identifier,
        "unique_id": local_identifier
    }
    merged_component = {**chargepoint_service.get_default_component(), **x_component}
    payload = json.dumps(merged_component)
    mqtt.publish(f"homeassistant/number/{local_identifier}/config", payload)

def max_current_sensor(
    mqtt,
    chargepoint_service: MqttDeviceService
):
    local_identifier = chargepoint_service.identifier + "_max_current"
    x_component = {
        "name": "Max current",
        "value_template": """
            {% if value_json.type == 'evt.max_current.report' %}
                {{ value_json.val }}
            {% else %}
                {{ this.state }}
            {% endif %}
        """,
        "unit_of_measurement": "A",
        "object_id": local_identifier,
        "unique_id": local_identifier
    }
    merged_component = {**chargepoint_service.get_default_component(), **x_component}
    payload = json.dumps(merged_component)
    mqtt.publish(f"homeassistant/sensor/{local_identifier}/config", payload)

def min_current_sensor(
    mqtt,
    chargepoint_service
):
    local_identifier = chargepoint_service.identifier + "_min_current"
    x_component = {
        "name": "Min current",
        "value_template": """
            6
        """,
        "unit_of_measurement": "A",
        "object_id": local_identifier,
        "unique_id": local_identifier
    }
    merged_component = {**chargepoint_service.get_default_component(), **x_component}
    payload = json.dumps(merged_component)
    mqtt.publish(f"homeassistant/sensor/{local_identifier}/config", payload)

def charging(
    mqtt,
    chargepoint_service,
):
    local_identifier = chargepoint_service.identifier + "_charging"
    x_component = {
        "name": "Charging",
        "command_topic": chargepoint_service.command_topic,
        "value_template": """
            {% if value_json.type == 'evt.state.report' %}
                {% if value_json.val == 'charging' %}
                    ON
                {% else %}
                    OFF
                {% endif %}
            {% else %}
                undefined
            {% endif %}
        """,
        "availability": {
            "topic": chargepoint_service.state_topic,
            "value_template": """
                {% if value_json.type == 'evt.state.report' %}
                    {% if value_json.val == 'charging' %}
                        online
                    {% elif value_json.val == 'ready_to_charge' %}
                        online
                    {% else %}
                        offline
                    {% endif %}
                {% else %}
                    undefined
                {% endif %}
            """,
        },
        "command_template": """
            {
                "src":"homeassistant",
                {% if value == "ON" %}
                    "type":"cmd.charge.start",
                {% else %}
                    "type":"cmd.charge.stop",
                {% endif %}
                "val": null,
                "val_t": "null",
                "serv": "chargepoint"
            }
        """,
        "object_id": local_identifier,
        "unique_id": local_identifier
    }
    merged_component = {**chargepoint_service.get_default_component(), **x_component}
    payload = json.dumps(merged_component)
    mqtt.publish(f"homeassistant/switch/{local_identifier}/config", payload)