import json
import sys
import time

import pyfimptoha.mqtt_client as fimp
import pyfimptoha.homeassistant as homeassistant

topic_discover = "pt:j1/mt:rsp/rt:app/rn:homeassistant/ad:flow1"

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        print(
            'Usage: \n"python run.py" to fetch data from FIMP and push components to Home Assistant'
        )
    else:
        print('Starting service...')
        f = fimp.MqttClient()
        print('Sleeping forever...')
        if not f.connect():
            print("MQTT client didn't connect... Exiting")
            exit(1)

        f.client.loop_start()

        path = "pyfimptoha/data/fimp_discover.json"
        topic = "pt:j1/mt:cmd/rt:app/rn:vinculum/ad:1"
        with open(path) as json_file:
            data = json.load(json_file)

        print('Asking FIMP to expose all devices, shortcuts, rooms and mode...')
        def is_correct(msg, data):
            return msg.topic == topic_discover
        response = f.send_and_wait(topic, topic_discover, data, is_correct)

        if data is not None:
            msg, data = response
            homeassistant.create_components(
                devices=data["val"]["param"]["device"],
                rooms=data["val"]["param"]["room"],
                shortcuts=data["val"]["param"]["shortcut"],
                mode=data["val"]["param"]["house"]["mode"],
                mqtt=f,
                selected_devices_mode=f._selected_devices_mode,
                selected_devices=f._selected_devices,
                debug=f._debug
            )

        while True:
            if not f.connected:
                print("MQTT client: No longer connected... Exiting")
                break
            time.sleep(1)
