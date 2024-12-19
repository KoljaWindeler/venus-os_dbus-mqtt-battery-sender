#!/usr/bin/env python

from gi.repository import GLib  # pyright: ignore[reportMissingImports]
#import platform
import logging
import sys
import os
#from time import sleep, time
import json
import paho.mqtt.client as mqtt
import configparser  # for config/ini file
import _thread
import dbus

# import Victron Energy packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), "ext", "velib_python"))
from vedbus import VeDbusService, VeDbusItemImport  # noqa: E402
from ve_utils import get_vrm_portal_id  # noqa: E402



# get values from config.ini file
try:
    config_file = (os.path.dirname(os.path.realpath(__file__))) + "/config.ini"
    if os.path.exists(config_file):
        config = configparser.ConfigParser()
        config.read(config_file)
        if config["MQTT"]["broker_address"] == "IP_ADDR_OR_FQDN":
            print('ERROR:The "config.ini" is using invalid default values like IP_ADDR_OR_FQDN. The driver restarts in 60 seconds.')
            sleep(60)
            sys.exit()
    else:
        print('ERROR:The "' + config_file + '" is not found. Did you copy or rename the "config.sample.ini" to "config.ini"? The driver restarts in 60 seconds.')
        sleep(60)
        sys.exit()

except Exception:
    exception_type, exception_object, exception_traceback = sys.exc_info()
    file = exception_traceback.tb_frame.f_code.co_filename
    line = exception_traceback.tb_lineno
    print(f"Exception occurred: {repr(exception_object)} of type {exception_type} in {file} line #{line}")
    print("ERROR:The driver restarts in 60 seconds.")
    sleep(60)
    sys.exit()


# Get logging level from config.ini
# ERROR = shows errors only
# WARNING = shows ERROR and warnings
# INFO = shows WARNING and running functions
# DEBUG = shows INFO and data/values
if "DEFAULT" in config and "logging" in config["DEFAULT"]:
    if config["DEFAULT"]["logging"] == "DEBUG":
        logging.basicConfig(level=logging.DEBUG)
    elif config["DEFAULT"]["logging"] == "INFO":
        logging.basicConfig(level=logging.INFO)
    elif config["DEFAULT"]["logging"] == "ERROR":
        logging.basicConfig(level=logging.ERROR)
    else:
        logging.basicConfig(level=logging.WARNING)
else:
    logging.basicConfig(level=logging.WARNING)


# get timeout
if "DEFAULT" in config and "timeout" in config["DEFAULT"]:
    timeout = int(config["DEFAULT"]["timeout"])
else:
    timeout = 60



# set variables
connected = 0


# formatting
def _a(p, v):
    return str("%.1f" % v) + "A"


def _ah(p, v):
    return str("%.1f" % v) + "Ah"


def _n(p, v):
    return str("%i" % v)


def _p(p, v):
    return str("%i" % v) + "%"


def _s(p, v):
    return str("%s" % v)


def _t(p, v):
    return str("%.1f" % v) + "°C"


def _v(p, v):
    return str("%.2f" % v) + "V"


def _v3(p, v):
    return str("%.3f" % v) + "V"


def _w(p, v):
    return str("%i" % v) + "W"


battery_dict = {
    # general data
    "/Dc/0/Power": {"value": None, "textformat": _w},
    "/Dc/0/Voltage": {"value": None, "textformat": _v},
    "/Dc/0/Current": {"value": None, "textformat": _a},
    "/Dc/0/Temperature": {"value": None, "textformat": _t},
    "/InstalledCapacity": {"value": None, "textformat": _ah},
    "/ConsumedAmphours": {"value": None, "textformat": _ah},
    "/Capacity": {"value": None, "textformat": _ah},
    "/Soc": {"value": None, "textformat": _p},
    "/TimeToGo": {"value": None, "textformat": _n},
    "/Balancing": {"value": None, "textformat": _n},
    "/SystemSwitch": {"value": None, "textformat": _n},
    # alarms
    "/Alarms/LowVoltage": {"value": 0, "textformat": _n},
    "/Alarms/HighVoltage": {"value": 0, "textformat": _n},
    "/Alarms/LowSoc": {"value": 0, "textformat": _n},
    "/Alarms/HighChargeCurrent": {"value": 0, "textformat": _n},
    "/Alarms/HighDischargeCurrent": {"value": 0, "textformat": _n},
    "/Alarms/HighCurrent": {"value": 0, "textformat": _n},
    "/Alarms/CellImbalance": {"value": 0, "textformat": _n},
    "/Alarms/HighChargeTemperature": {"value": 0, "textformat": _n},
    "/Alarms/LowChargeTemperature": {"value": 0, "textformat": _n},
    "/Alarms/LowCellVoltage": {"value": 0, "textformat": _n},
    "/Alarms/LowTemperature": {"value": 0, "textformat": _n},
    "/Alarms/HighTemperature": {"value": 0, "textformat": _n},
    "/Alarms/FuseBlown": {"value": 0, "textformat": _n},
    # info
    "/Info/ChargeRequest": {"value": None, "textformat": _n},
    "/Info/MaxChargeVoltage": {"value": None, "textformat": _v},
    "/Info/MaxChargeCurrent": {"value": None, "textformat": _a},
    "/Info/MaxDischargeCurrent": {"value": None, "textformat": _a},
    # history
    "/History/ChargeCycles": {"value": None, "textformat": _n},
    "/History/MinimumVoltage": {"value": None, "textformat": _v},
    "/History/MaximumVoltage": {"value": None, "textformat": _v},
    "/History/TotalAhDrawn": {"value": None, "textformat": _ah},
    # system
    "/System/MinVoltageCellId": {"value": None, "textformat": _s},
    "/System/MinCellVoltage": {"value": None, "textformat": _v3},
    "/System/MaxVoltageCellId": {"value": None, "textformat": _s},
    "/System/MaxCellVoltage": {"value": None, "textformat": _v3},
    "/System/MinTemperatureCellId": {"value": None, "textformat": _s},
    "/System/MinCellTemperature": {"value": None, "textformat": _t},
    "/System/MaxTemperatureCellId": {"value": None, "textformat": _s},
    "/System/MaxCellTemperature": {"value": None, "textformat": _t},
    "/System/MOSTemperature": {"value": None, "textformat": _t},
    "/System/NrOfModulesOnline": {"value": 1, "textformat": _n},
    "/System/NrOfModulesOffline": {"value": 0, "textformat": _n},
    "/System/NrOfModulesBlockingCharge": {"value": 0, "textformat": _n},
    "/System/NrOfModulesBlockingDischarge": {"value": 0, "textformat": _n},
    # cell voltages
    "/Voltages/Sum": {"value": None, "textformat": _v},
    "/Voltages/Diff": {"value": None, "textformat": _v3},
    "/Voltages/Cell1": {"value": None, "textformat": _v3},
    "/Voltages/Cell2": {"value": None, "textformat": _v3},
    "/Voltages/Cell3": {"value": None, "textformat": _v3},
    "/Voltages/Cell4": {"value": None, "textformat": _v3},
    "/Voltages/Cell5": {"value": None, "textformat": _v3},
    "/Voltages/Cell6": {"value": None, "textformat": _v3},
    "/Voltages/Cell7": {"value": None, "textformat": _v3},
    "/Voltages/Cell8": {"value": None, "textformat": _v3},
    "/Voltages/Cell9": {"value": None, "textformat": _v3},
    "/Voltages/Cell10": {"value": None, "textformat": _v3},
    "/Voltages/Cell11": {"value": None, "textformat": _v3},
    "/Voltages/Cell12": {"value": None, "textformat": _v3},
    "/Voltages/Cell13": {"value": None, "textformat": _v3},
    "/Voltages/Cell14": {"value": None, "textformat": _v3},
    "/Voltages/Cell15": {"value": None, "textformat": _v3},
    "/Voltages/Cell16": {"value": None, "textformat": _v3},
    "/Voltages/Cell17": {"value": None, "textformat": _v3},
    "/Voltages/Cell18": {"value": None, "textformat": _v3},
    "/Voltages/Cell19": {"value": None, "textformat": _v3},
    "/Voltages/Cell20": {"value": None, "textformat": _v3},
    "/Voltages/Cell21": {"value": None, "textformat": _v3},
    "/Voltages/Cell22": {"value": None, "textformat": _v3},
    "/Voltages/Cell23": {"value": None, "textformat": _v3},
    "/Voltages/Cell24": {"value": None, "textformat": _v3},
    "/Balances/Cell1": {"value": None, "textformat": _n},
    "/Balances/Cell2": {"value": None, "textformat": _n},
    "/Balances/Cell3": {"value": None, "textformat": _n},
    "/Balances/Cell4": {"value": None, "textformat": _n},
    "/Balances/Cell5": {"value": None, "textformat": _n},
    "/Balances/Cell6": {"value": None, "textformat": _n},
    "/Balances/Cell7": {"value": None, "textformat": _n},
    "/Balances/Cell8": {"value": None, "textformat": _n},
    "/Balances/Cell9": {"value": None, "textformat": _n},
    "/Balances/Cell10": {"value": None, "textformat": _n},
    "/Balances/Cell11": {"value": None, "textformat": _n},
    "/Balances/Cell12": {"value": None, "textformat": _n},
    "/Balances/Cell13": {"value": None, "textformat": _n},
    "/Balances/Cell14": {"value": None, "textformat": _n},
    "/Balances/Cell15": {"value": None, "textformat": _n},
    "/Balances/Cell16": {"value": None, "textformat": _n},
    "/Balances/Cell17": {"value": None, "textformat": _n},
    "/Balances/Cell18": {"value": None, "textformat": _n},
    "/Balances/Cell19": {"value": None, "textformat": _n},
    "/Balances/Cell20": {"value": None, "textformat": _n},
    "/Balances/Cell21": {"value": None, "textformat": _n},
    "/Balances/Cell22": {"value": None, "textformat": _n},
    "/Balances/Cell23": {"value": None, "textformat": _n},
    "/Balances/Cell24": {"value": None, "textformat": _n},
    # IO
    "/Io/AllowToCharge": {"value": None, "textformat": _n},
    "/Io/AllowToDischarge": {"value": None, "textformat": _n},
    "/Io/AllowToBalance": {"value": None, "textformat": _n},
    "/Io/ExternalRelay": {"value": None, "textformat": _n},
}


# MQTT requests
def on_disconnect(client, userdata, rc):
    global connected
    logging.warning("MQTT client: Got disconnected")
    if rc != 0:
        logging.warning("MQTT client: Unexpected MQTT disconnection. Will auto-reconnect")
    else:
        logging.warning("MQTT client: rc value:" + str(rc))

    while connected == 0:
        try:
            logging.warning(f"MQTT client: Trying to reconnect to broker {config['MQTT']['broker_address']} on port {config['MQTT']['broker_port']}")
            client.connect(host=config["MQTT"]["broker_address"], port=int(config["MQTT"]["broker_port"]))
            connected = 1
        except Exception as err:
            logging.error(f"MQTT client: Error in retrying to connect with broker ({config['MQTT']['broker_address']}:{config['MQTT']['broker_port']}): {err}")
            logging.error("MQTT client: Retrying in 15 seconds")
            connected = 0
            sleep(15)


def on_connect(client, userdata, flags, rc):
    global connected
    if rc == 0:
        logging.info("MQTT client: Connected to MQTT broker!")
        connected = 1
        client.subscribe(config["MQTT"]["topic"])
    else:
        logging.error("MQTT client: Failed to connect, return code %d\n", rc)



class DbusMqttBatterySenderService:
    def __init__(
        self,
        battery_path,
        mqtt_topic,
    ):

        self._battery_path = battery_path
		self._mqtt_topic = mqtt_topic
		
        GLib.timeout_add(1000, self._update)  # pause 1000ms before the next request

    def _update(self):

        global battery_dict
		global connected
		
		dbus_conn = dbus.SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else dbus.SystemBus()
		dbus_prefix = "com.victronenergy.battery." % self._battery_path
		dbus_item_value = VeDbusItemImport(dbus_conn, dev, dbus_path).get_value()
		battery_dict_dbus = {}
		# read all current values
		for item_path in battery_dict:
			if item_path in dbus_item:
				battery_dict_dbus.append(item_path:{"value": battery_dict[item_path]})
			
		if connected:
			result = client.publish(self._mqtt_topic, json.dumps(battery_dict))
			if result[0] == 0:
				logging.debug(f"Send `{json.dumps(battery_dict)}` to topic `{self._mqtt_topic}`")
			else:
				logging.debug(f"Failed to send message to topic {self._mqtt_topic}")
        return True


def main():
    _thread.daemon = True  # allow the program to quit

    from dbus.mainloop.glib import (
        DBusGMainLoop,
    )  # pyright: ignore[reportMissingImports]

    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)

    # MQTT setup
    client = mqtt.Client("MqttBatterySender_" + get_vrm_portal_id() + "_" + str(config["DEFAULT"]["battery_path"]))
    client.on_disconnect = on_disconnect
    client.on_connect = on_connect

    # check tls and use settings, if provided
    if "tls_enabled" in config["MQTT"] and config["MQTT"]["tls_enabled"] == "1":
        logging.info("MQTT client: TLS is enabled")

        if "tls_path_to_ca" in config["MQTT"] and config["MQTT"]["tls_path_to_ca"] != "":
            logging.info('MQTT client: TLS: custom ca "%s" used' % config["MQTT"]["tls_path_to_ca"])
            client.tls_set(config["MQTT"]["tls_path_to_ca"], tls_version=2)
        else:
            client.tls_set(tls_version=2)

        if "tls_insecure" in config["MQTT"] and config["MQTT"]["tls_insecure"] != "":
            logging.info("MQTT client: TLS certificate server hostname verification disabled")
            client.tls_insecure_set(True)

    # check if username and password are set
    if "username" in config["MQTT"] and "password" in config["MQTT"] and config["MQTT"]["username"] != "" and config["MQTT"]["password"] != "":
        logging.info('MQTT client: Using username "%s" and password to connect' % config["MQTT"]["username"])
        client.username_pw_set(username=config["MQTT"]["username"], password=config["MQTT"]["password"])

    # connect to broker
    logging.info(f"MQTT client: Connecting to broker {config['MQTT']['broker_address']} on port {config['MQTT']['broker_port']}")
    client.connect(host=config["MQTT"]["broker_address"], port=int(config["MQTT"]["broker_port"]))
    client.loop_start()

    DbusMqttBatterySenderService(
        battery_path=config["DEFAULT"]["battery_path"],
        mqtt_topic=config["MQTT"]["topic"],
    )

    logging.info("Connected to dbus and switching over to GLib.MainLoop() (= event based)")
    mainloop = GLib.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()