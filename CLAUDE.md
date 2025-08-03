# MeshCore MQTT Bridge - Claude Context

## Project Overview

This project is a **MeshCore MQTT Bridge** - a robust Python application that bridges MeshCore mesh networking devices to MQTT brokers, enabling seamless integration with IoT platforms and message processing systems.

### Key Features
- **Multi-connection support**: TCP, Serial, and BLE connections to MeshCore devices
- **Flexible configuration**: JSON/YAML files, environment variables, CLI arguments
- **Configurable event system**: Subscribe to specific MeshCore event types
- **Robust MQTT integration**: Authentication, QoS, retention, auto-reconnection
- **Async architecture**: Built with Python asyncio for high performance
- **Type safety**: Full type annotations with mypy support
- **Comprehensive testing**: 59+ tests with pytest and pytest-asyncio

## Architecture

### Core Components

1. **Configuration System** (`meshcore_mqtt/config.py`)
   - Pydantic-based configuration with validation
   - Support for multiple input methods (file, env, CLI)
   - Event type validation and normalization

2. **Bridge Core** (`meshcore_mqtt/bridge.py`)
   - Main bridge logic connecting MeshCore to MQTT
   - Event handler system with configurable subscriptions
   - Safe MQTT publishing with error handling
   - JSON serialization with comprehensive fallbacks

3. **CLI Interface** (`meshcore_mqtt/main.py`)
   - Click-based command line interface
   - Logging configuration for third-party libraries
   - Configuration loading with precedence handling

### Event System

The bridge supports configurable event subscriptions:

**Default Events**:
- `CONTACT_MSG_RECV`, `CHANNEL_MSG_RECV` (messages)
- `CONNECTED`, `DISCONNECTED` (connection status)
- `LOGIN_SUCCESS`, `LOGIN_FAILED` (authentication)
- `DEVICE_INFO`, `BATTERY`, `NEW_CONTACT` (device info)
- `MESSAGES_WAITING` (notifications)

**Additional Events**:
- `ADVERTISEMENT`, `TELEMETRY`, `POSITION`
- `ROUTING`, `ADMIN`, `USER`
- `TEXT_MESSAGE_RX`, `TEXT_MESSAGE_TX`
- `WAYPOINT`, `NEIGHBOR_INFO`, `TRACEROUTE`
- `NODE_LIST_CHANGED`, `CONFIG_CHANGED`

### Auto-Fetch Restart Feature

The bridge automatically handles `NO_MORE_MSGS` events from MeshCore by restarting the auto-fetch mechanism after a configurable delay:

- **Purpose**: Prevents message fetching from stopping when MeshCore reports no more messages
- **Configuration**: `auto_fetch_restart_delay` (1-60 seconds, default: 5)
- **Behavior**: When `NO_MORE_MSGS` is received, waits the configured delay then restarts auto-fetching
- **Environment Variable**: `MESHCORE_AUTO_FETCH_RESTART_DELAY=10`
- **CLI Argument**: `--meshcore-auto-fetch-restart-delay 10`

### MQTT Topics

The bridge publishes to structured MQTT topics:
- `{prefix}/message` - Contact/channel messages
- `{prefix}/status` - Connection status
- `{prefix}/advertisement` - Device advertisements
- `{prefix}/battery` - Battery updates
- `{prefix}/device_info` - Device information
- `{prefix}/new_contact` - Contact discovery
- `{prefix}/login` - Authentication status
- `{prefix}/command/{type}` - Commands (subscribed)

### MQTT Command System

The bridge supports bidirectional communication via MQTT commands. Send commands to `{prefix}/command/{command_type}` with JSON payloads:

**Message Commands**:
- `send_msg` - Send direct message
  ```json
  {"destination": "node_id_or_contact_name", "message": "Hello!"}
  ```
- `send_channel_msg` - Send channel/group message
  ```json
  {"channel": "channel_name", "message": "Hello group!"}
  ```

**Device Commands**:
- `device_query` - Query device information
  ```json
  {}
  ```
- `get_battery` - Get battery status
  ```json
  {}
  ```
- `set_name` - Set device name
  ```json
  {"name": "MyDevice"}
  ```
- `set_tx_power` - Set transmission power
  ```json
  {"power": 10}
  ```
- `advertise` - Trigger device advertisement
  ```json
  {}
  ```

**Network Commands**:
- `ping` - Ping a node
  ```json
  {"destination": "node_id"}
  ```
- `traceroute` - Trace route to node
  ```json
  {"destination": "node_id"}
  ```

**Contact Commands**:
- `get_contacts` - Get contact list
  ```json
  {}
  ```
- `get_contact_by_name` - Find contact by name
  ```json
  {"name": "John"}
  ```
- `get_contact_by_key` - Find contact by key prefix
  ```json
  {"key_prefix": "abcd1234"}
  ```

**Command Examples**:
```bash
# Send direct message
mosquitto_pub -h localhost -t "meshcore/command/send_msg" \
  -m '{"destination": "Alice", "message": "Hello Alice!"}'

# Send channel message
mosquitto_pub -h localhost -t "meshcore/command/send_channel_msg" \
  -m '{"channel": "general", "message": "Hello everyone!"}'

# Ping a node
mosquitto_pub -h localhost -t "meshcore/command/ping" \
  -m '{"destination": "node123"}'

# Get device info
mosquitto_pub -h localhost -t "meshcore/command/device_query" -m '{}'
```

## Development Guidelines

### Code Quality Tools

The project uses these tools (configured in `pyproject.toml`):
- **Black**: Code formatting (line length: 88)
- **Flake8**: Linting with custom rules
- **MyPy**: Type checking with strict settings
- **Pytest**: Testing with asyncio support
- **Pre-commit**: Automated code quality checks

### Testing Strategy

**Test Structure**:
- `tests/test_config.py` - Configuration system (18 tests)
- `tests/test_bridge.py` - Bridge functionality (10 tests)
- `tests/test_configurable_events.py` - Event configuration (13 tests)
- `tests/test_json_serialization.py` - JSON handling (10 tests)
- `tests/test_logging.py` - Logging configuration (6 tests)

**Key Test Areas**:
- Configuration validation and loading
- Event handler mapping and subscription
- JSON serialization edge cases
- MQTT topic generation
- Logging setup and third-party library control

### Running Commands

**Development Setup**:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install
```

**Testing**:
```bash
pytest                      # Run all tests
pytest -v                   # Verbose output
pytest --cov=meshcore_mqtt  # With coverage
pytest tests/test_config.py # Specific test file
```

**Code Quality**:
```bash
black meshcore_mqtt/ tests/     # Format code
flake8 meshcore_mqtt/ tests/    # Lint code
mypy meshcore_mqtt/ tests/      # Type check
pre-commit run --all-files      # Run all checks
```

**Running the Application**:
```bash
# With config file
python -m meshcore_mqtt.main --config-file config.yaml

# With CLI arguments
python -m meshcore_mqtt.main \
  --mqtt-broker localhost \
  --meshcore-connection tcp \
  --meshcore-address 192.168.1.100 \
  --meshcore-events "CONNECTED,BATTERY,ADVERTISEMENT"

# With environment variables
python -m meshcore_mqtt.main --env
```

## Recent Development History

### Major Features Implemented

1. **JSON Serialization (6b492db)**
   - Robust JSON serialization handling all Python data types
   - Fallback mechanisms for complex objects
   - Comprehensive error handling and validation

2. **Configurable Events (f7c10cc)**
   - Made MeshCore event types configurable
   - Support for config files, env vars, and CLI args
   - Case-insensitive event parsing with validation
   - Enhanced logging configuration for third-party libraries

3. **ADVERTISEMENT Events (91f06d8)**
   - Added dedicated MQTT topic for device advertisements
   - Specific event handler for advertisement broadcasts
   - Updated documentation and configuration examples

### Code Patterns

**Event Handler Pattern**:
```python
async def _on_meshcore_[event_type](self, event_data: Any) -> None:
    """Handle [event_type] events."""
    self.logger.debug(f"Received MeshCore {event_type}")

    topic = f"{self.config.mqtt.topic_prefix}/[topic_name]"
    payload = self._serialize_to_json(event_data)
    self._safe_mqtt_publish(topic, payload)
```

**Configuration Validation**:
```python
@field_validator("field_name")
@classmethod
def validate_field(cls, v: Type) -> Type:
    """Validate field with custom logic."""
    # Validation logic here
    return v
```

## Important Notes for Claude

### When Making Changes

1. **Always run tests** after changes: `pytest -v`
2. **Follow existing patterns** for event handlers and configuration
3. **Update documentation** when adding new features
4. **Use type hints** for all new code
5. **Handle errors gracefully** with proper logging

### Configuration Precedence
1. Command-line arguments (highest)
2. Configuration file
3. Environment variables (lowest)

### Event Handler Guidelines
- Use `_safe_mqtt_publish()` for all MQTT publishing
- Use `_serialize_to_json()` for payload serialization
- Log at appropriate levels (debug for data, info for status)
- Follow the established naming pattern: `_on_meshcore_[event_name]`

### Testing Requirements
- Add tests for new event handlers
- Test configuration validation
- Test error conditions and edge cases
- Maintain high test coverage

### Logging Best Practices
- Use structured logging with proper levels
- Configure third-party library logging appropriately
- Provide meaningful log messages for debugging
- Use `self.logger` instance for consistency

This project demonstrates modern Python development practices with async programming, comprehensive testing, and robust error handling. The codebase is well-structured and maintainable, with clear separation of concerns and extensive documentation.
