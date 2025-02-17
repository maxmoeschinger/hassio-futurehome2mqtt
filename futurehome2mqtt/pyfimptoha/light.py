import json
from pyfimptoha.helpers.MqttDevice import MqttDevice

def new_light_v2(mqtt, device: MqttDevice):
    if not device.has_service("out_bin_switch"):
        print("Missing out_bin_switch service for lightning")
        return

    has_color_control = device.has_service("color_ctrl")
    has_level_control = device.has_service("out_lvl_switch")
    device_services = device.get_services()

    main_service = device_services["out_lvl_switch"] if has_level_control else device_services["out_bin_switch"]

    payload_on = '{"serv":"out_bin_switch","type":"cmd.binary.set","val":true,"val_t":"bool","src":"homeassistant"}'
    payload_off = '{"serv":"out_bin_switch","type":"cmd.binary.set","val":false,"val_t":"bool","src":"homeassistant"}'
    light_component = {
        # "schema": "template",
        "state_topic": device_services["out_bin_switch"].state_topic,
        "command_topic": device_services["out_bin_switch"].command_topic,
        "state_value_template": "{% if value_json.val %}" + payload_on + "{% else %}" + payload_off + "{% endif %}",
        "payload_on": payload_on,
        "payload_off": payload_off
    }

    if has_level_control:
        light_component = {
            **light_component,
            "brightness_state_topic": device_services["out_lvl_switch"].state_topic,
            "brightness_command_topic": device_services["out_lvl_switch"].command_topic,
            "brightness_value_template": "{{ value_json.val | int }}",
            "brightness_command_template": """
                {
                    "props":{},
                    "serv":"out_lvl_switch",
                    "tags":[],
                    "type":"cmd.lvl.set",
                    "val": {{ value | int }},
                    "val_t": "int",
                    "src":"homeassistant"
                }
            """
        }

    if has_color_control:
        color_ctrl = device_services["color_ctrl"]
        components = color_ctrl.service_data["props"]["sup_components"]
        if "temp" in components:
            light_component = {
                **light_component,
                "color_temp_kelvin": True,
                "color_temp_state_topic": color_ctrl.state_topic,
                "color_temp_command_topic": color_ctrl.command_topic,
                "color_temp_value_template": "{{ (1000000 / value_json.val.temp) | int }}",
                "color_temp_command_template": """
                    {
                        "props":{},
                        "serv":"color_ctrl",
                        "tags":[],
                        "type":"cmd.color.set",
                        "val": {
                            "temp": {{ (1000000 / value) | int }},
                        },
                        "val_t": "int_map",
                        "src":"homeassistant"
                    }
                """
            }

    payload = json.dumps({**main_service.get_default_component(), **light_component})
    mqtt.publish(f"homeassistant/light/{main_service.identifier}/config", payload)

    return device.get_reports_info(["color_ctrl", "out_lvl_switch", "out_bin_switch"])
