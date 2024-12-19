# dbus-mqtt-battery-sender - Driver to send battery data to mqtt, as counterpart to https://github.com/mr-manuel/venus-os_dbus-mqtt-battery

<small>GitHub repository: [koljawindeler/venus-os_dbus-mqtt-battery-sender](https://github.com/koljawindeler/venus-os_dbus-mqtt-battery-sender)</small>

## Index

1. [Disclaimer](#disclaimer)
1. [Supporting/Sponsoring this project](#supportingsponsoring-this-project)
1. [Purpose](#purpose)
1. [Config](#config)
1. [JSON structure](#json-structure)
1. [Install / Update](#install--update)
1. [Uninstall](#uninstall)
1. [Restart](#restart)
1. [Debugging](#debugging)



## Disclaimer

I wrote this script for myself. I'm not responsible, if you damage something using my script.


## Supporting/Sponsoring this project

This project is highly copied from @mr-manuel, thanks for your support!

## Purpose

The script runs invisible in the background and sends the data of a dedicated battery to an mqtt server. 
Basically the idea is to act as a couterpart to https://github.com/mr-manuel/venus-os_dbus-mqtt-battery so two VRM instances can see the same battery data.


## Config

Copy or rename the `config.sample.ini` to `config.ini` in the `dbus-mqtt-battery-sender` folder and change it as you need it.


## Install / Update

1. Login to your Venus OS device via SSH. See [Venus OS:Root Access](https://www.victronenergy.com/live/ccgx:root_access#root_access) for more details.

2. Execute this commands to download and copy the files:

    ```bash
    wget -O /tmp/download_dbus-mqtt-battery-sender.sh https://raw.githubusercontent.com/koljawindeler/venus-os_dbus-mqtt-battery-sender/master/download.sh

    bash /tmp/download_dbus-mqtt-battery-sender.sh
    ```

3. Select the version you want to install.

4. Press enter for a single instance. For multiple instances, enter a number and press enter.

    Example:

    - Pressing enter or entering `1` will install the driver to `/data/etc/dbus-mqtt-battery-sender`.
    - Entering `2` will install the driver to `/data/etc/dbus-mqtt-battery-sender-2`.

### Extra steps for your first installation

5. Edit the config file to fit your needs. The correct command for your installation is shown after the installation.

    - If you pressed enter or entered `1` during installation:
    ```bash
    nano /data/etc/dbus-mqtt-battery-sender/config.ini
    ```

    - If you entered `2` during installation:
    ```bash
    nano /data/etc/dbus-mqtt-battery-sender-2/config.ini
    ```

6. Install the driver as a service. The correct command for your installation is shown after the installation.

    - If you pressed enter or entered `1` during installation:
    ```bash
    bash /data/etc/dbus-mqtt-battery-sender/install.sh
    ```

    - If you entered `2` during installation:
    ```bash
    bash /data/etc/dbus-mqtt-battery-sender-2/install.sh
    ```

    The daemon-tools should start this service automatically within seconds.

## Uninstall

⚠️ If you have multiple instances, ensure you choose the correct one. For example:

- To uninstall the default instance:
    ```bash
    bash /data/etc/dbus-mqtt-battery-sender/uninstall.sh
    ```

- To uninstall the second instance:
    ```bash
    bash /data/etc/dbus-mqtt-battery-sender-2/uninstall.sh
    ```

## Restart

⚠️ If you have multiple instances, ensure you choose the correct one. For example:

- To restart the default instance:
    ```bash
    bash /data/etc/dbus-mqtt-battery-sender/restart.sh
    ```

- To restart the second instance:
    ```bash
    bash /data/etc/dbus-mqtt-battery-sender-2/restart.sh
    ```

## Debugging

⚠️ If you have multiple instances, ensure you choose the correct one.

The logs can be checked with `tail -n 100 -f /data/log/dbus-mqtt-battery-sender/current | tai64nlocal`

The service status can be checked with svstat `svstat /service/dbus-mqtt-battery-sender`

This will output somethink like `/service/dbus-mqtt-battery-sender: up (pid 5845) 185 seconds`

If the seconds are under 5 then the service crashes and gets restarted all the time. If you do not see anything in the logs you can increase the log level in `/data/etc/dbus-mqtt-battery-sender/dbus-mqtt-battery-sender.py` by changing `level=logging.WARNING` to `level=logging.INFO` or `level=logging.DEBUG`

If the script stops with the message `dbus.exceptions.NameExistsException: Bus name already exists: com.victronenergy.battery.mqtt_battery"` it means that the service is still running or another service is using that bus name.

