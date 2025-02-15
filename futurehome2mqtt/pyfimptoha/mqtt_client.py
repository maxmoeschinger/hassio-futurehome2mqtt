import json
import os
import time
import uuid
from typing import Callable

from dotenv import load_dotenv

import paho.mqtt.client as mqtt

class MqttCallback:
    def __init__(self, topic_to_subscribe=None, on_dict_message=None):
        self._on_dict_message = on_dict_message
        self.topic_to_subscribe = topic_to_subscribe
        self.last_dict_message = None

    def on_message(self, msg):
        payload = str(msg.payload.decode("utf-8"))
        data = None
        try:
            data = json.loads(payload)
        except json.decoder.JSONDecodeError:
            pass

        if self._on_dict_message and data is not None:
            data = self._on_dict_message(msg, data)
            if data is not None:
                self.last_dict_message = data

class MqttClient:
    def __init__(self):
        load_dotenv()

        self.connected: bool = False
        self._server: str = os.environ.get('FIMP_SERVER')
        self._username: str = os.environ.get('FIMP_USERNAME')
        self._password: str = os.environ.get('FIMP_PASSWORD')
        self._port: int = int(os.environ.get('FIMP_PORT'))
        self._client_id: str = os.environ.get('CLIENT_ID')
        self._debug: bool = os.environ.get('DEBUG')
        self._selected_devices_mode: str = os.environ.get('SELECTED_DEVICES_MODE')
        self._selected_devices: list = os.environ.get('SELECTED_DEVICES').split(',')
        self._topic_discover: str = "pt:j1/mt:rsp/rt:app/rn:homeassistant/ad:flow1"
        self.on_message_callbacks = {}

        if self._debug.lower() == "true":
            self._debug = True
        else:
            self._debug = False

        print('Connecting to: ' + self._server)
        print('Username: ', self._username)
        print('Port: ', self._port)
        print('Client id: ', self._client_id)
        print('Debug: ', self._debug)
        print('Selected devices mode: ', self._selected_devices_mode)
        print('Selected devices: ', self._selected_devices)

    def connect(self):
        self.client = mqtt.Client(client_id=self._client_id)
        self.client.loop_start()

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        self.client.username_pw_set(self._username, self._password)
        self.client.connect(self._server, self._port, 60)
        time.sleep(2)

        return self.connected

    def on_connect(self, client, userdata, flags, rc):
        """
        The callback for when the client receives a CONNACK response from the server.
        """
        if rc == 0:
            self.connected = True
            print("MQTT client: Connected successfully")

            # Subscribe to Home Assistant status where Home Assistant announces restarts
            self.client.subscribe("homeassistant/status")

            # Request FIMP devices
            self.client.subscribe(self._topic_discover)

    def publish_dict(self, topic, data):
        payload = json.dumps(data)
        self.publish(topic, payload)

    def publish(self, topic, payload):
        self.client.publish(topic, payload)

    def on_message(self, client, userdata, msg):
        """
        The callback for when a message is received from the server.
        """
        for clbk in self.on_message_callbacks.values():
            clbk.on_message(msg)

    def send_and_wait(self, command_topic, event_topic, data, is_correct: Callable, timeout=5):
        def on_message(msg, data):
            if not is_correct(msg, data):
                return None

            return msg, data

        callback = MqttCallback(
            on_dict_message=on_message,
            topic_to_subscribe=event_topic,
        )
        self.add_callback(callback)
        self.publish_dict(command_topic, data)

        start_time = time.time()
        end_time = start_time + timeout
        while time.time() < end_time and callback.last_dict_message is None:
            time.sleep(0.1)

        return callback.last_dict_message

    def on_disconnect(self, client, userdata, rc):
        """
        The callback for when the client disconnects from the server.
        """

        self.connected = False
        print(f"MQTT client: Disconnected... Result code: {str(rc)}.")

    def add_callback(self, callback: MqttCallback):
        id = str(uuid.uuid4())
        self.on_message_callbacks[id] = callback

        if callback.topic_to_subscribe is not None:
            self.client.subscribe(callback.topic_to_subscribe)

        return id

    def remove_callback(self, id):
        if id in self.on_message_callbacks:
            if self.on_message_callbacks[id].topic_to_subscribe is not None:
                self.client.unsubscribe(self.on_message_callbacks[id].topic_to_subscribe)

            self.on_message_callbacks.pop(id)
