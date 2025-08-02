# MeshCore MQTT Bridge

A robust bridge service that connects MeshCore devices to MQTT brokers, enabling seamless integration with IoT platforms and message processing systems.

## Features

- **Multiple Connection Types**: Support for TCP, Serial, and BLE connections to MeshCore devices
- **Flexible Configuration**: JSON, YAML, environment variables, and command-line configuration options
- **MQTT Integration**: Full MQTT client with authentication, QoS, and retention support
- **Async Architecture**: Built with Python asyncio for high performance
- **Type Safety**: Full type annotations with mypy support
- **Comprehensive Testing**: Unit tests with pytest and pytest-asyncio
- **Code Quality**: Pre-commit hooks, black formatting, flake8 linting

## Installation

### From Source

```bash
git clone <repository-url>
cd meshcore-mqtt
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Development Installation

```bash
pip install -r requirements-dev.txt
pre-commit install
```

## Configuration

The bridge supports multiple configuration methods with the following precedence:
1. Command-line arguments (highest priority)
2. Configuration file (JSON or YAML)
3. Environment variables (lowest priority)

### Configuration Options

#### MQTT Settings
- `mqtt_broker`: MQTT broker address (required)
- `mqtt_port`: MQTT broker port (default: 1883)
- `mqtt_username`: MQTT authentication username (optional)
- `mqtt_password`: MQTT authentication password (optional)
- `mqtt_topic_prefix`: MQTT topic prefix (default: "meshcore")
- `mqtt_qos`: Quality of Service level 0-2 (default: 0)
- `mqtt_retain`: Message retention flag (default: false)

#### MeshCore Settings
- `meshcore_connection`: Connection type (serial, ble, tcp)
- `meshcore_address`: Device address (required)
- `meshcore_port`: Device port for TCP connections (default: 12345)
- `meshcore_baudrate`: Baudrate for serial connections (default: 115200)
- `meshcore_timeout`: Operation timeout in seconds (default: 5)
- `meshcore_events`: List of MeshCore event types to subscribe to (see [Event Types](#event-types))

#### General Settings
- `log_level`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### Configuration Examples

#### JSON Configuration (config.json)
```json
{
  "mqtt": {
    "broker": "mqtt.example.com",
    "port": 1883,
    "username": "myuser",
    "password": "mypass",
    "topic_prefix": "meshcore",
    "qos": 1,
    "retain": false
  },
  "meshcore": {
    "connection_type": "tcp",
    "address": "192.168.1.100",
    "port": 12345,
    "baudrate": 115200,
    "timeout": 10,
    "events": [
      "CONTACT_MSG_RECV",
      "CHANNEL_MSG_RECV",
      "CONNECTED",
      "DISCONNECTED",
      "BATTERY",
      "DEVICE_INFO"
    ]
  },
  "log_level": "INFO"
}
```

#### YAML Configuration (config.yaml)
```yaml
mqtt:
  broker: mqtt.example.com
  port: 1883
  username: myuser
  password: mypass
  topic_prefix: meshcore
  qos: 1
  retain: false

meshcore:
  connection_type: tcp
  address: "192.168.1.100"
  port: 12345
  baudrate: 115200
  timeout: 10
  events:
    - CONTACT_MSG_RECV
    - CHANNEL_MSG_RECV
    - CONNECTED
    - DISCONNECTED
    - BATTERY
    - DEVICE_INFO

log_level: INFO
```

#### Environment Variables
```bash
export MQTT_BROKER=mqtt.example.com
export MQTT_PORT=1883
export MQTT_USERNAME=myuser
export MQTT_PASSWORD=mypass
export MESHCORE_CONNECTION=tcp
export MESHCORE_ADDRESS=192.168.1.100
export MESHCORE_PORT=12345
export MESHCORE_BAUDRATE=115200
export MESHCORE_EVENTS="CONNECTED,DISCONNECTED,BATTERY,DEVICE_INFO"
export LOG_LEVEL=INFO
```

## Usage

### Command Line Interface

#### Using Configuration File
```bash
python -m meshcore_mqtt.main --config-file config.json
```

#### Using Command Line Arguments
```bash
python -m meshcore_mqtt.main \
  --mqtt-broker mqtt.example.com \
  --mqtt-username myuser \
  --mqtt-password mypass \
  --meshcore-connection tcp \
  --meshcore-address 192.168.1.100 \
  --meshcore-port 12345 \
  --meshcore-events "CONNECTED,DISCONNECTED,BATTERY"
```

#### Using Environment Variables
```bash
python -m meshcore_mqtt.main --env
```

### Connection Types

#### TCP Connection
```bash
python -m meshcore_mqtt.main \
  --mqtt-broker localhost \
  --meshcore-connection tcp \
  --meshcore-address 192.168.1.100 \
  --meshcore-port 12345
```

#### Serial Connection
```bash
python -m meshcore_mqtt.main \
  --mqtt-broker localhost \
  --meshcore-connection serial \
  --meshcore-address /dev/ttyUSB0 \
  --meshcore-baudrate 9600
```

#### BLE Connection
```bash
python -m meshcore_mqtt.main \
  --mqtt-broker localhost \
  --meshcore-connection ble \
  --meshcore-address AA:BB:CC:DD:EE:FF
```

## Event Types

The bridge can subscribe to various MeshCore event types. You can configure which events to monitor using the `events` configuration option.

### Default Events
If no events are specified, the bridge subscribes to these default events:
- `CONTACT_MSG_RECV` - Contact messages received
- `CHANNEL_MSG_RECV` - Channel messages received  
- `CONNECTED` - Device connection events
- `DISCONNECTED` - Device disconnection events
- `LOGIN_SUCCESS` - Successful authentication
- `LOGIN_FAILED` - Failed authentication
- `MESSAGES_WAITING` - Pending messages notification
- `DEVICE_INFO` - Device information updates
- `BATTERY` - Battery status updates
- `NEW_CONTACT` - New contact discovered

### Additional Supported Events
You can also subscribe to these additional event types:
- `TELEMETRY` - Telemetry data
- `POSITION` - Position/GPS updates
- `USER` - User-related events
- `ROUTING` - Mesh routing events
- `ADMIN` - Administrative messages
- `TEXT_MESSAGE_RX` - Text messages received
- `TEXT_MESSAGE_TX` - Text messages transmitted
- `WAYPOINT` - Waypoint data
- `NEIGHBOR_INFO` - Neighbor node information
- `TRACEROUTE` - Network trace information
- `NODE_LIST_CHANGED` - Node list updates
- `CONFIG_CHANGED` - Configuration changes
- `ADVERTISEMENT` - Device advertisement broadcasts

### Configuration Examples

#### Minimal Events (Performance Optimized)
```yaml
meshcore:
  events:
    - CONNECTED
    - DISCONNECTED
    - BATTERY
```

#### Message-Focused Events
```yaml
meshcore:
  events:
    - CONTACT_MSG_RECV
    - CHANNEL_MSG_RECV
    - TEXT_MESSAGE_RX
```

#### Full Monitoring
```yaml
meshcore:
  events:
    - CONTACT_MSG_RECV
    - CHANNEL_MSG_RECV
    - CONNECTED
    - DISCONNECTED
    - TELEMETRY
    - POSITION
    - BATTERY
    - DEVICE_INFO
    - ADVERTISEMENT
```

**Note**: Event names are case-insensitive. You can use `connected`, `CONNECTED`, or `Connected` - they will all be normalized to uppercase.

## MQTT Topics

The bridge publishes to different MQTT topics based on the configured event types. Using the configured topic prefix (default: "meshcore"):

### Core Topics
- `{prefix}/message` - Messages from CONTACT_MSG_RECV and CHANNEL_MSG_RECV events
- `{prefix}/status` - Connection status from CONNECTED/DISCONNECTED events  
- `{prefix}/command/{type}` - Commands to MeshCore device (subscribed)

### Event-Specific Topics
- `{prefix}/login` - Authentication status from LOGIN_SUCCESS/LOGIN_FAILED events
- `{prefix}/device_info` - Device information from DEVICE_INFO events
- `{prefix}/battery` - Battery status from BATTERY events
- `{prefix}/new_contact` - Contact discovery from NEW_CONTACT events
- `{prefix}/advertisement` - Device advertisements from ADVERTISEMENT events
- `{prefix}/debug_event` - Other events not specifically handled

### Examples
- `meshcore/message` - Incoming contact/channel messages
- `meshcore/status` - Device connection status ("connected"/"disconnected")
- `meshcore/battery` - Battery level updates
- `meshcore/device_info` - Device specifications and capabilities
- `meshcore/advertisement` - Device advertisement broadcasts
- `meshcore/command/send` - Send command to MeshCore (subscribed topic)

## Development

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=meshcore_mqtt

# Run specific test file
pytest tests/test_config.py -v
```

### Code Quality
```bash
# Format code
black meshcore_mqtt/ tests/

# Lint code
flake8 meshcore_mqtt/ tests/

# Type checking
mypy meshcore_mqtt/ tests/

# Run pre-commit hooks
pre-commit run --all-files
```

## Architecture

The bridge consists of three main components:

1. **Configuration System** (`config.py`)
   - Pydantic-based configuration with validation
   - Support for JSON, YAML, environment variables, and CLI args
   - Type-safe configuration with proper defaults

2. **Bridge Core** (`bridge.py`)
   - Async event-driven architecture
   - MQTT client management with reconnection
   - MeshCore device connection handling
   - Message routing between MQTT and MeshCore

3. **CLI Interface** (`main.py`)
   - Click-based command line interface
   - Configuration loading and validation
   - Logging setup and error handling

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Support

For issues and questions, please open an issue on the GitHub repository.