#!/usr/bin/env python

from gi.repository import GLib  # pyright: ignore[reportMissingImports]
#import platform
import logging
import sys
import os
from time import sleep
import json
import paho.mqtt.client as mqtt
import configparser  # for config/ini file
import _thread
import dbus

# import Victron Energy packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), "ext", "velib_python"))
from vedbus import VeDbusService, VeDbusItemImport  # noqa: E402
from ve_utils import get_vrm_portal_id  # noqa: E402

skiplist = []
skiplist.append("CurrentAvg")
skiplist.append("FirmwareVersion")
skiplist.append("HardwareVersion")
skiplist.append("Connected")
skiplist.append("Serial")
skiplist.append("CustomName")
skiplist.append("DeviceName")
skiplist.append("Temperature1")
skiplist.append("Temperature2")
skiplist.append("Temperature3")
skiplist.append("Temperature4")
skiplist.append("Temperature1Name")
skiplist.append("Temperature2Name")
skiplist.append("Temperature3Name")
skiplist.append("Temperature4Name")
skiplist.append("ProcessVersion")
skiplist.append("ProcessName")
skiplist.append("Connection")
skiplist.append("DeviceInstance")
skiplist.append("ProductId")
skiplist.append("ProductName")
skiplist.append("ChargeMode")
skiplist.append("ChargeModeDebug")
skiplist.append("BatteryLowVoltage")
skiplist.append("ChargeLimitation")
skiplist.append("DischargeLimitation")
skiplist.append("NrOfCellsPerBattery")
skiplist.append("ForceChargingOff")
skiplist.append("ForceDischargingOff")
skiplist.append("TurnBalancingOff")
skiplist.append("BmsCable")

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
        mqtt_client
    ):

        self._battery_path = battery_path
        self._mqtt_topic = mqtt_topic
        self._mqtt_client = mqtt_client
        GLib.timeout_add(3000, self._update)  # pause 1000ms before the next request

    def _update(self):
        global battery_dict
        global connected
        global skiplist
        # Load values from dbus
        dbus_conn = dbus.SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else dbus.SystemBus()
        dev = "com.victronenergy.battery." + self._battery_path
        try:
          dbus_items = VeDbusItemImport(dbus_conn, dev, "/").get_value()
        except:
          dbus_items = {}
          logging.info("battery not (yet) found")

        # reformat dbus to mqtt
        battery_dict_mqtt = {}
        for dbus_path, dbus_value in dbus_items.items():
           dbus_path = dbus_path.replace("/0/","/")
           path = dbus_path.split('/')
           if(len(path)==1):
              if(path[0] in skiplist or dbus_value is None):
                 continue
              battery_dict_mqtt.update({path[0]:dbus_value})
           elif(len(path)==2):
              if(path[1] in skiplist or dbus_value is None):
                 continue
              battery_subdict_mqtt = {}
              if path[0] in battery_dict_mqtt:
                 battery_subdict_mqtt = battery_dict_mqtt[path[0]]
              battery_subdict_mqtt.update({path[1]:dbus_value})
              battery_dict_mqtt.update({path[0]:battery_subdict_mqtt})

        # Push to MQTT
        if connected:
           result = self._mqtt_client.publish(self._mqtt_topic, json.dumps(battery_dict_mqtt))
           if result[0] == 0:
              logging.debug(f"Send `{json.dumps(battery_dict_mqtt)[0:50]}...` to topic `{self._mqtt_topic}`")
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
        mqtt_client=client
    )

    logging.info("Connected to dbus and switching over to GLib.MainLoop() (= event based)")
    mainloop = GLib.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()
