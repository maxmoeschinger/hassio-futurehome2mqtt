class MqttDeviceService:
    def __init__(self, device, service_name, service_data):
        self.device = device
        self.service_data = service_data
        self.service_name = service_name
        self.identifier = f"fh_{self.device.id}_{self.device.adapter}_{self.device.address}_{service_name}"
        self.state_topic = f"pt:j1/mt:evt{self.service_data['addr']}"
        self.command_topic = f"pt:j1/mt:cmd{self.service_data['addr']}"
        self.intf = self.service_data['intf'] if 'intf' in self.service_data else None

    def get_default_component(self):
        return {
            "name": None,
            "object_id": self.identifier,
            "unique_id": self.identifier,
            "device": {
                "identifiers": f"{self.device.adapter}_{self.device.address}",
                "name": f"{self.device.clientName}",
                "suggested_area": f"{self.device.room_alias}",
                "hw_version": f"{self.device.model}",
                "model": f"{self.device.model_alias}",
                "sw_version": f"{self.device.adapter}_{self.device.address}"
            },
            "state_topic": self.state_topic,
        }

    def get_common_params(self):
        return {
            # "mqtt": mqtt,
            "device": self.device,
            "state_topic": self.state_topic,
            "identifier": self.identifier,
            "default_component": self.get_default_component()
        }

    def get_reports_info(self):
        return [[self.command_topic, self.service_name, s] for s in self.service_data["intf"] if s.endswith(".get_report")]
