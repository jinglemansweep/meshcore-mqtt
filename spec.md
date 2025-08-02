# MeshCore to MQTT Bridge

This document describes the MeshCore to MQTT Bridge, which allows communication between MeshCore devices and MQTT brokers.

## Requirements

* Python 3.11 or later
  * `paho-mqtt` library for MQTT communication
  * `meshcore_py` library for MeshCore device interaction (https://github.com/fdlamotte/meshcore_py)
  * `asyncio` for asynchronous programming
  * `click` for command-line argument parsing
  * `pydantic` for configuration and validation
  * `pytest` for testing
  * `flake8` for code style checking
  * `black` for code formatting
  * `mypy` for type checking
  * `pre-commit` for managing pre-commit hooks

## Code Quality

* All code should have type annotations and adhere to PEP 8 style guidelines.
* Unit tests should be written for all new features and bug fixes.
* Code should be formatted using `black`.
* Code should be checked for type errors using `mypy`.
* Code should be checked for style issues using `flake8`.
* Code should be tested using `pytest`.

## Configuration

Configuration should be provided using command-line arguments, environment variables, or a configuration file. The configuration can be specified in a JSON or YAML format.

The following configuration options are available:

* `mqtt_broker`: The MQTT broker address (e.g., `mqtt.example.com`).
* `mqtt_port`: The MQTT broker port (default is `1883`).
* `mqtt_username`: The username for MQTT authentication (optional).
* `mqtt_password`: The password for MQTT authentication (optional).
* `meshcore_connection`: The type of connection to the MeshCore device (e.g., `serial`, `ble`, `tcp`).
* `meshcore_address`: The address of the MeshCore device (e.g., `/dev/ttyUSB0` for serial, `00:11:22:33:44:55` for BLE, `192.168.1.100` for TCP).
* `meshcore_port`: The port for the MeshCore device (default is `12345` for TCP).
* `meshcore_timeout`: The timeout for MeshCore operations (default is `5` seconds).
* `mqtt_topic_prefix`: The prefix for MQTT topics (default is `meshcore`).
* `mqtt_qos`: The Quality of Service level for MQTT messages (default is `0`).
* `mqtt_retain`: Whether to retain MQTT messages (default is `False`).
