from pyfimptoha.helpers.MqttDeviceService import MqttDeviceService


def get_adapter_name(device):
    if device["fimp"]["adapter"] == "zwave-ad":
        adapter = "zw"
    elif device["fimp"]["adapter"] == "zigbee":
        adapter = "zb"
    else:
        adapter = device["fimp"]["adapter"]
    return adapter

class MqttDevice(object):
    def __init__(self, device_data, room_alias):
        self.device_data = device_data
        self.room_alias = room_alias
        self.model = device_data["model"] if device_data.get("model") and device_data["model"] else ""
        self.model_alias = device_data["modelAlias"] if device_data.get("modelAlias") and device_data["modelAlias"] else self.model
        self.adapter = get_adapter_name(device_data)
        self.id = device_data["id"]
        self.address = device_data["fimp"]["address"]
        self.clientName = device_data["client"]["name"]
        self.functionality = device_data["functionality"]

    def has_service(self, service_name):
        return service_name in self.device_data["services"]

    def get_services(self):
        services = {}
        for service_name, service in self.device_data["services"].items():
            services[service_name] = MqttDeviceService(self, service_name, service)

        return services

    def get_service(self, service_name):
        services = self.get_services()

        if service_name in services:
            return services[service_name]

        return None

    def get_reports_info(self, whitelist):
        services_reports_info = [service.get_reports_info() for service_name, service in self.get_services().items() if service_name in whitelist]
        merged = []
        for service_reports_info in services_reports_info:
            merged.extend(service_reports_info)

        return merged