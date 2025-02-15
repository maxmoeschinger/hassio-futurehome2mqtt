import json
import typing

def get_max_current(mqtt, command_topic, state_topic):
    def is_correct(msg, data):
        return "type" in data and data["type"] == "evt.max_current.report"

    d = mqtt.send_and_wait(
        command_topic,
        state_topic,
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
    device: typing.Any,
    service_name,
    state_topic,
    identifier,
    default_component,
    command_topic
):
    if "evt.max_current.report" in device["services"][service_name]["intf"]:
        max_current_sensor(mqtt, device, service_name, state_topic, identifier, default_component, command_topic)

    max_current = get_max_current(mqtt, command_topic, state_topic)
    if max_current is None:
        print("Could not determine max_current")
        return

    if "evt.cable_lock.report" in device["services"][service_name]["intf"]:
        cable_lock(mqtt, device, service_name, state_topic, identifier, default_component, command_topic)
    if "evt.state.report" in device["services"][service_name]["intf"]:
        state(mqtt, device, service_name, state_topic, identifier, default_component, command_topic)
    if "evt.current_session.report" in device["services"][service_name]["intf"]:
        current(mqtt, device, service_name, state_topic, identifier, default_component, command_topic, max_current)
    if "cmd.charge.start" in device["services"][service_name]["intf"] and "cmd.charge.stop" in device["services"][service_name]["intf"]:
        charging(mqtt, device, service_name, state_topic, identifier, default_component, command_topic, max_current)

    min_current_sensor(mqtt, device, service_name, state_topic, identifier, default_component, command_topic)

def cable_lock(
        mqtt,
        device,
        service_name,
        state_topic,
        identifier,
        default_component,
        command_topic
):
    local_identifier = identifier + "_cable_lock"
    lock_component = {
        "command_topic": command_topic,
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
    merged_component = {**default_component, **lock_component}
    payload = json.dumps(merged_component)
    mqtt.publish(f"homeassistant/lock/{local_identifier}/config", payload)


def state(
        mqtt,
        device,
        service_name,
        state_topic,
        identifier,
        default_component,
        command_topic
):
    local_identifier = identifier + "_state"
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
    merged_component = {**default_component, **x_component}
    payload = json.dumps(merged_component)
    mqtt.publish(f"homeassistant/sensor/{local_identifier}/config", payload)

def current(
    mqtt,
    device,
    service_name,
    state_topic,
    identifier,
    default_component,
    command_topic,
    max_current
):
    local_identifier = identifier + "_current"
    x_component = {
        "name": "Charge current",
        "command_topic": command_topic,
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
    merged_component = {**default_component, **x_component}
    payload = json.dumps(merged_component)
    mqtt.publish(f"homeassistant/number/{local_identifier}/config", payload)

def max_current_sensor(
    mqtt,
    device,
    service_name,
    state_topic,
    identifier,
    default_component,
    command_topic
):
    local_identifier = identifier + "_max_current"
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
    merged_component = {**default_component, **x_component}
    payload = json.dumps(merged_component)
    mqtt.publish(f"homeassistant/sensor/{local_identifier}/config", payload)

def min_current_sensor(
    mqtt,
    device,
    service_name,
    state_topic,
    identifier,
    default_component,
    command_topic
):
    local_identifier = identifier + "_min_current"
    x_component = {
        "name": "Min current",
        "value_template": """
            6
        """,
        "unit_of_measurement": "A",
        "object_id": local_identifier,
        "unique_id": local_identifier
    }
    merged_component = {**default_component, **x_component}
    payload = json.dumps(merged_component)
    mqtt.publish(f"homeassistant/sensor/{local_identifier}/config", payload)

def charging(
    mqtt,
    device,
    service_name,
    state_topic,
    identifier,
    default_component,
    command_topic,
    max_current
):
    local_identifier = identifier + "_charging"
    x_component = {
        "name": "Charging",
        "command_topic": command_topic,
        "value_template": """
            {% if value_json.type == 'evt.state.report' %}
                {% if value_json.val == 'charging' %}
                    ON
                {% elif value_json.val == 'ready_to_charge' %}
                    OFF
                {% else %}
                    offline
                {% endif %}
            {% else %}
                {{ this.state }}
            {% endif %}
        """,
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
    merged_component = {**default_component, **x_component}
    payload = json.dumps(merged_component)
    mqtt.publish(f"homeassistant/switch/{local_identifier}/config", payload)