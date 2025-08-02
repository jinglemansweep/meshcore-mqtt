# MeshCore MQTT Bridge

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![CI](https://github.com/jinglemansweep/meshcore-mqtt/actions/workflows/ci.yml/badge.svg)](https://github.com/jinglemansweep/meshcore-mqtt/actions/workflows/ci.yml)
[![Code Quality](https://github.com/jinglemansweep/meshcore-mqtt/actions/workflows/code-quality.yml/badge.svg)](https://github.com/jinglemansweep/meshcore-mqtt/actions/workflows/code-quality.yml)
[![Tests](https://github.com/jinglemansweep/meshcore-mqtt/actions/workflows/test.yml/badge.svg)](https://github.com/jinglemansweep/meshcore-mqtt/actions/workflows/test.yml)
[![Code style: black](https://img.shields.io/badge/Code%20style-black-000000.svg)](https://github.com/psf/black)
[![Typing: mypy](https://img.shields.io/badge/Typing-mypy-blue.svg)](https://mypy.readthedocs.io/)
[![Security: bandit](https://img.shields.io/badge/Security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

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

## Docker Deployment

The MeshCore MQTT Bridge provides multi-stage Docker support with Alpine Linux for minimal image size and enhanced security. Following 12-factor app principles, the Docker container is configured entirely through environment variables.

### Docker Features

- **Multi-stage build**: Optimized Alpine-based images with minimal attack surface
- **Non-root user**: Runs as dedicated `meshcore` user for security
- **Environment variables**: Full configuration via environment variables (12-factor app)
- **Health checks**: Built-in container health monitoring
- **Signal handling**: Proper init system with tini for clean shutdowns
- **Container logging**: Logs output to stdout/stderr for Docker log drivers

### Quick Start with Docker

#### Using Pre-built Images from GHCR

Pre-built Docker images are available from GitHub Container Registry:

**Available Tags:**
- `latest` - Latest stable release from main branch
- `develop` - Latest development build
- `v1.0.0` - Specific version tags
- `v1.0` - Major.minor version tags
- `v1` - Major version tags

```bash
# Pull the latest image
docker pull ghcr.io/jinglemansweep/meshcore-mqtt:latest

# Run with serial connection (default for MeshCore devices)
docker run -d \
  --name meshcore-mqtt-bridge \
  --restart unless-stopped \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  -e MQTT_BROKER=192.168.1.100 \
  -e MQTT_USERNAME=meshcore \
  -e MQTT_PASSWORD=meshcore123 \
  -e MESHCORE_CONNECTION=serial \
  -e MESHCORE_ADDRESS=/dev/ttyUSB0 \
  ghcr.io/jinglemansweep/meshcore-mqtt:latest
```

#### Building Locally

```bash
# Build the image locally
docker build -t meshcore-mqtt:latest .

# Run with local image
docker run -d \
  --name meshcore-mqtt-bridge \
  --restart unless-stopped \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  -e MQTT_BROKER=192.168.1.100 \
  -e MQTT_USERNAME=meshcore \
  -e MQTT_PASSWORD=meshcore123 \
  -e MESHCORE_CONNECTION=serial \
  -e MESHCORE_ADDRESS=/dev/ttyUSB0 \
  meshcore-mqtt:latest
```

#### Using Environment File

```bash
# Create environment file from example
cp .env.docker.example .env.docker
# Edit .env.docker with your configuration

# Run with environment file (includes device mount for serial)
docker run -d \  
  --name meshcore-mqtt-bridge \
  --restart unless-stopped \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  --env-file .env.docker \
  ghcr.io/jinglemansweep/meshcore-mqtt:latest
```

#### Option 3: Using Docker Compose
```bash
# Start the entire stack with MQTT broker
docker-compose up -d

# View logs
docker-compose logs -f meshcore-mqtt

# Stop the stack
docker-compose down
```


### Docker Environment Variables

All configuration options can be set via environment variables:

```bash
# Logging Configuration
LOG_LEVEL=INFO

# MQTT Broker Configuration
MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_USERNAME=user
MQTT_PASSWORD=pass
MQTT_TOPIC_PREFIX=meshcore
MQTT_QOS=1
MQTT_RETAIN=true

# MeshCore Device Configuration (serial default)
MESHCORE_CONNECTION=serial
MESHCORE_ADDRESS=/dev/ttyUSB0    # Serial port, IP address, or BLE MAC address
MESHCORE_BAUDRATE=115200         # For serial connections
MESHCORE_PORT=4403              # Only for TCP connections
MESHCORE_TIMEOUT=30

# Event Configuration (comma-separated)
MESHCORE_EVENTS=CONNECTED,DISCONNECTED,BATTERY,DEVICE_INFO
```

#### Connection Type Examples

**Serial Connection (Default):**
```bash
MESHCORE_CONNECTION=serial
MESHCORE_ADDRESS=/dev/ttyUSB0
MESHCORE_BAUDRATE=115200
# Note: Use --device=/dev/ttyUSB0 in docker run for device access
```

**TCP Connection:**
```bash
MESHCORE_CONNECTION=tcp
MESHCORE_ADDRESS=192.168.1.100
MESHCORE_PORT=4403
```

**BLE Connection:**
```bash
MESHCORE_CONNECTION=ble
MESHCORE_ADDRESS=AA:BB:CC:DD:EE:FF
```


### Health Monitoring

The container includes health checks:

```bash
# Check container health
docker inspect --format='{{.State.Health.Status}}' meshcore-mqtt-bridge

# View health check logs
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' meshcore-mqtt-bridge
```

### Container Management

```bash
# View container logs
docker logs -f meshcore-mqtt-bridge

# Execute commands in container
docker exec -it meshcore-mqtt-bridge sh

# Stop container
docker stop meshcore-mqtt-bridge

# Remove container
docker rm meshcore-mqtt-bridge
```

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

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Support

For issues and questions, please open an issue on the GitHub repository.