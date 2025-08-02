"""Core bridge implementation between MeshCore and MQTT."""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt
from meshcore import (
    BLEConnection,
    ConnectionManager,
    EventType,
    MeshCore,
    SerialConnection,
    TCPConnection,
)

from .config import Config, ConnectionType


class MeshCoreMQTTBridge:
    """Bridge between MeshCore devices and MQTT brokers."""

    def __init__(self, config: Config) -> None:
        """Initialize the bridge with configuration."""
        self.config = config
        self.logger = logging.getLogger(__name__)

        # MeshCore components
        self.meshcore: Optional[MeshCore] = None
        self.connection_manager: Optional[ConnectionManager] = None

        # MQTT components
        self.mqtt_client: Optional[mqtt.Client] = None

        # State management
        self._running = False
        self._tasks: list[asyncio.Task[Any]] = []

        # Connection health monitoring
        self._meshcore_connected = False
        self._mqtt_connected = False
        self._last_meshcore_activity: Optional[float] = None
        self._last_mqtt_activity: Optional[float] = None
        self._auto_fetch_running = False

        # Separate reconnection tracking
        self._mqtt_reconnect_attempts = 0
        self._meshcore_reconnect_attempts = 0
        self._max_reconnect_attempts = 10

        # MQTT reconnection flags
        self._mqtt_reconnecting = False

    async def start(self) -> None:
        """Start the bridge service."""
        if self._running:
            self.logger.warning("Bridge is already running")
            return

        self.logger.info("Starting MeshCore MQTT Bridge")

        try:
            # Initialize MQTT client
            await self._setup_mqtt()

            # Initialize MeshCore connection
            await self._setup_meshcore()

            # Start the bridge loops
            self._running = True

            # Start connection monitoring task
            monitor_task = asyncio.create_task(self._monitor_connections())
            self._tasks.append(monitor_task)

            # Start persistent auto-fetch task
            autofetch_task = asyncio.create_task(self._maintain_auto_fetch())
            self._tasks.append(autofetch_task)

            await self._run_bridge()

        except Exception as e:
            self.logger.error(f"Failed to start bridge: {e}")
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop the bridge service."""
        if not self._running:
            return

        self.logger.info("Stopping MeshCore MQTT Bridge")
        self._running = False

        # Cancel all running tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        # Disconnect from MeshCore
        if self.meshcore:
            try:
                await self.meshcore.stop_auto_message_fetching()
                await self.meshcore.disconnect()
            except Exception as e:
                self.logger.error(f"Error disconnecting from MeshCore: {e}")

        # Disconnect from MQTT
        if self.mqtt_client:
            try:
                # Stop the loop first
                if hasattr(self.mqtt_client, "_loop_started"):
                    self.mqtt_client.loop_stop()
                    delattr(self.mqtt_client, "_loop_started")

                # Then disconnect
                if self.mqtt_client.is_connected():
                    self.mqtt_client.disconnect()
            except Exception as e:
                self.logger.error(f"Error disconnecting from MQTT: {e}")

        self.logger.info("Bridge stopped")

    async def _setup_mqtt(self) -> None:
        """Set up MQTT client connection."""
        self.logger.info("Setting up MQTT connection")

        # Generate a unique client ID for MQTT connection
        client_id = f"meshcore-mqtt-{uuid.uuid4().hex[:8]}"
        self.logger.debug(f"Using MQTT client ID: {client_id}")

        self.mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            clean_session=True,  # Use clean session to avoid broker issues
            reconnect_on_failure=True,
        )

        # Set up MQTT callbacks
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect  # type: ignore
        self.mqtt_client.on_message = self._on_mqtt_message
        self.mqtt_client.on_publish = self._on_mqtt_publish
        self.mqtt_client.on_log = self._on_mqtt_log

        # Set authentication if provided
        if self.config.mqtt.username and self.config.mqtt.password:
            self.mqtt_client.username_pw_set(
                self.config.mqtt.username, self.config.mqtt.password
            )

        # Set connection parameters for better stability
        self.mqtt_client.keepalive = 60  # Back to standard 60s for stability
        self.mqtt_client.max_inflight_messages_set(1)  # Limit to 1 message at a time
        self.mqtt_client.max_queued_messages_set(100)  # Limit queue size

        # Enable automatic reconnection with retry parameters
        self.mqtt_client.reconnect_delay_set(min_delay=1, max_delay=30)

        # Connect to MQTT broker with retry logic
        try:
            await self._connect_mqtt_with_retry()
        except Exception as e:
            self.logger.error(f"Initial MQTT connection failed: {e}")
            # Use the robust recovery system for initial connection too
            await self._recover_mqtt_connection()

        # Start MQTT loop in a separate task
        mqtt_task = asyncio.create_task(self._mqtt_loop())
        self._tasks.append(mqtt_task)

    async def _connect_mqtt_with_retry(self, max_retries: int = 5) -> None:
        """Connect to MQTT broker with retry logic."""
        for attempt in range(max_retries):
            try:
                if self.mqtt_client:
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.mqtt_client.connect(  # type: ignore
                            self.config.mqtt.broker, self.config.mqtt.port, 60
                        ),
                    )
                    self.logger.info(
                        f"Connected to MQTT broker on attempt {attempt + 1}"
                    )
                    return
            except Exception as e:
                self.logger.warning(
                    f"MQTT connection attempt {attempt + 1} failed: {e}"
                )
                if attempt < max_retries - 1:
                    delay = min(2**attempt, 30)  # Exponential backoff, max 30s
                    self.logger.info(f"Retrying MQTT connection in {delay} seconds")
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(
                        f"Failed to connect to MQTT broker after {max_retries} "
                        f"attempts: {e}"
                    )

    async def _setup_meshcore(self) -> None:
        """Set up MeshCore connection."""
        self.logger.info("Setting up MeshCore connection")

        # Create appropriate connection based on configuration
        if self.config.meshcore.connection_type == ConnectionType.TCP:
            connection = TCPConnection(
                self.config.meshcore.address, self.config.meshcore.port or 12345
            )
        elif self.config.meshcore.connection_type == ConnectionType.SERIAL:
            connection = SerialConnection(
                self.config.meshcore.address, self.config.meshcore.baudrate
            )
        elif self.config.meshcore.connection_type == ConnectionType.BLE:
            connection = BLEConnection(self.config.meshcore.address)
        else:
            raise ValueError(
                f"Unsupported connection type: {self.config.meshcore.connection_type}"
            )

        # Initialize connection manager and MeshCore
        self.connection_manager = ConnectionManager(connection)

        # Enable debug logging only if log level is DEBUG
        debug_logging = self.config.log_level == "DEBUG"

        self.meshcore = MeshCore(
            self.connection_manager,
            debug=debug_logging,  # Enable debug logging based on config
            auto_reconnect=True,  # Enable auto-reconnect
            default_timeout=self.config.meshcore.timeout,
        )

        # Ensure MeshCore logger respects our configured log level
        meshcore_logger = logging.getLogger("meshcore")
        meshcore_logger.setLevel(getattr(logging, self.config.log_level))

        # Set up MeshCore event handlers based on configuration
        self.logger.info("Setting up MeshCore event subscriptions")
        configured_events = set(self.config.meshcore.events)

        # Map event type strings to handlers
        event_handlers = {
            "CONTACT_MSG_RECV": self._on_meshcore_message,
            "CHANNEL_MSG_RECV": self._on_meshcore_message,
            "CONNECTED": self._on_meshcore_connected,
            "DISCONNECTED": self._on_meshcore_disconnected,
            "LOGIN_SUCCESS": self._on_meshcore_login_success,
            "LOGIN_FAILED": self._on_meshcore_login_failed,
            "MESSAGES_WAITING": self._on_meshcore_messages_waiting,
            "DEVICE_INFO": self._on_meshcore_device_info,
            "BATTERY": self._on_meshcore_battery,
            "NEW_CONTACT": self._on_meshcore_new_contact,
            "ADVERTISEMENT": self._on_meshcore_advertisement,
        }

        # Always subscribe to NO_MORE_MSGS to restart auto-fetching
        try:
            no_more_msgs_event = getattr(EventType, "NO_MORE_MSGS")
            self.meshcore.subscribe(no_more_msgs_event, self._on_meshcore_no_more_msgs)
            self.logger.info("Subscribed to NO_MORE_MSGS event for auto-fetch restart")
        except AttributeError:
            self.logger.warning("NO_MORE_MSGS event type not available")

        # Subscribe to configured events with specific handlers
        subscribed_events = set()
        for event_name in configured_events:
            try:
                event_type = getattr(EventType, event_name)
                handler = event_handlers.get(event_name, self._on_meshcore_debug_event)
                self.meshcore.subscribe(event_type, handler)
                subscribed_events.add(event_name)
                self.logger.info(f"Subscribed to event: {event_name}")
            except AttributeError:
                self.logger.warning(f"Unknown event type: {event_name}")

        # Connect to MeshCore device
        try:
            await self.meshcore.connect()
            self.logger.info("Connected to MeshCore device")
            self._meshcore_connected = True
            self._last_meshcore_activity = time.time()

            # Start auto message fetching to receive events
            await self.meshcore.start_auto_message_fetching()
            self.logger.info("Started auto message fetching")
            self._auto_fetch_running = True
        except Exception as e:
            raise RuntimeError(f"Failed to connect to MeshCore device: {e}")

    async def _run_bridge(self) -> None:
        """Run the main bridge loop."""
        self.logger.info("Bridge is now running")

        try:
            # MQTT subscriptions are handled in the on_connect callback
            # to ensure they persist through reconnections

            # Keep running until stopped
            while self._running:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            self.logger.info("Bridge loop cancelled")
        except Exception as e:
            self.logger.error(f"Error in bridge loop: {e}")
            raise

    async def _mqtt_loop(self) -> None:
        """Run MQTT client loop with connection monitoring."""
        if not self.mqtt_client:
            return

        self.logger.info("Starting MQTT client loop")

        try:
            # Start the network loop in background thread
            self.mqtt_client.loop_start()

            # Monitor connection health and ensure messages are processed
            while self._running:
                if self.mqtt_client:
                    # Check connection health every 5 seconds
                    if not self.mqtt_client.is_connected():
                        self.logger.warning(
                            "MQTT client disconnected in loop, attempting reconnection"
                        )
                        if self._running:
                            asyncio.create_task(self._recover_mqtt_connection())

                    # Give time for message processing
                    await asyncio.sleep(5.0)
                else:
                    break

        except Exception as e:
            self.logger.error(f"MQTT loop error: {e}")
        finally:
            # Stop the loop when exiting
            if self.mqtt_client:
                try:
                    self.mqtt_client.loop_stop()
                    self.logger.info("MQTT client loop stopped")
                except Exception as e:
                    self.logger.error(f"Error stopping MQTT loop: {e}")

    def _on_mqtt_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Dict[str, Any],
        rc: int,
        properties: Any = None,
    ) -> None:
        """Handle MQTT connection."""
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
            self._mqtt_connected = True
            self._last_mqtt_activity = time.time()
            # Resubscribe to command topics on reconnect
            command_topic = f"{self.config.mqtt.topic_prefix}/command/+"
            client.subscribe(command_topic, self.config.mqtt.qos)
            self.logger.info(f"Subscribed to MQTT topic: {command_topic}")
        else:
            self.logger.error(f"Failed to connect to MQTT broker: {rc}")
            self._mqtt_connected = False

    def _on_mqtt_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Dict[str, Any],
        rc: int,
        properties: Any = None,
    ) -> None:
        """Handle MQTT disconnection."""
        self._mqtt_connected = False
        if rc != 0:
            self.logger.warning(
                f"🔴 Unexpected MQTT disconnection: {mqtt.error_string(rc)} (code: {rc})"
            )
            # Only trigger recovery if we're not already reconnecting
            if self._running and not self._mqtt_reconnecting:
                self.logger.info("Triggering MQTT recovery from disconnect callback")
                asyncio.create_task(self._recover_mqtt_connection())
        else:
            self.logger.info("MQTT client disconnected cleanly")

    async def _monitor_connections(self) -> None:
        """Monitor both MeshCore and MQTT connections and attempt recovery."""
        self.logger.info("Starting connection monitoring")

        while self._running:
            try:
                current_time = time.time()

                # Check MQTT connection
                if self.mqtt_client and not self.mqtt_client.is_connected():
                    if self._mqtt_connected and not self._mqtt_reconnecting:
                        self.logger.warning(
                            "🔴 MQTT connection lost, starting recovery"
                        )
                        self._mqtt_connected = False
                        asyncio.create_task(self._recover_mqtt_connection())
                elif self.mqtt_client and self.mqtt_client.is_connected():
                    if not self._mqtt_connected and not self._mqtt_reconnecting:
                        self.logger.info("🟢 MQTT connection restored")
                        self._mqtt_connected = True
                        self._mqtt_reconnect_attempts = (
                            0  # Reset counter on natural restore
                        )
                        self._last_mqtt_activity = current_time

                # Check MeshCore connection
                meshcore_healthy = await self._check_meshcore_health()
                if not meshcore_healthy and self._meshcore_connected:
                    self.logger.warning("MeshCore connection lost, attempting recovery")
                    self._meshcore_connected = False
                    asyncio.create_task(self._recover_meshcore_connection())
                elif meshcore_healthy and not self._meshcore_connected:
                    self.logger.info("MeshCore connection restored")
                    self._meshcore_connected = True
                    self._last_meshcore_activity = current_time

                # Check for stale connections (no activity for 5 minutes)
                if (
                    self._last_meshcore_activity
                    and current_time - self._last_meshcore_activity > 300
                ):
                    self.logger.warning(
                        "MeshCore connection appears stale, forcing reconnection"
                    )
                    asyncio.create_task(self._recover_meshcore_connection())

                if (
                    self._last_mqtt_activity
                    and current_time - self._last_mqtt_activity > 300
                ):
                    self.logger.warning(
                        "MQTT connection appears stale, forcing reconnection"
                    )
                    asyncio.create_task(self._recover_mqtt_connection())

                # Sleep before next check
                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                self.logger.error(f"Error in connection monitoring: {e}")
                await asyncio.sleep(30)

    async def _check_meshcore_health(self) -> bool:
        """Check if MeshCore connection is healthy."""
        if not self.meshcore:
            return False

        try:
            # Try a simple operation to check if connection is alive
            # This is a basic check - in a real implementation you might
            # want to send a ping or status request
            return (
                hasattr(self.meshcore, "connection_manager")
                and self.meshcore.connection_manager is not None
            )
        except Exception:
            return False

    async def _recover_mqtt_connection(self) -> None:
        """Attempt to recover MQTT connection with complete client recreation."""
        # Prevent multiple concurrent recovery attempts
        if self._mqtt_reconnecting:
            self.logger.debug("MQTT recovery already in progress, skipping")
            return

        if self._mqtt_reconnect_attempts >= self._max_reconnect_attempts:
            self.logger.error("Max MQTT reconnection attempts reached")
            return

        self._mqtt_reconnecting = True
        self._mqtt_reconnect_attempts += 1

        self.logger.warning(
            f"Starting MQTT recovery (attempt "
            f"{self._mqtt_reconnect_attempts}/{self._max_reconnect_attempts})"
        )

        try:
            # 1. Completely destroy the old client
            await self._destroy_mqtt_client()

            # 2. Wait with exponential backoff
            delay = min(2**self._mqtt_reconnect_attempts, 30)
            self.logger.info(f"Waiting {delay}s before MQTT reconnection")
            await asyncio.sleep(delay)

            # 3. Create completely new MQTT client and connection
            await self._create_fresh_mqtt_client()

            # 4. Success - reset counters and flags
            self._mqtt_reconnect_attempts = 0
            self._mqtt_reconnecting = False
            self._mqtt_connected = True
            self._last_mqtt_activity = time.time()

            self.logger.info("✅ MQTT connection recovery successful")

        except Exception as e:
            self.logger.error(
                f"❌ MQTT recovery attempt {self._mqtt_reconnect_attempts} failed: {e}"
            )
            self._mqtt_reconnecting = False

            # Schedule retry if we haven't hit max attempts
            if self._mqtt_reconnect_attempts < self._max_reconnect_attempts:
                retry_delay = min(5 * self._mqtt_reconnect_attempts, 60)
                self.logger.info(f"Scheduling MQTT retry in {retry_delay}s")
                await asyncio.sleep(retry_delay)
                if self._running:  # Only retry if bridge is still running
                    asyncio.create_task(self._recover_mqtt_connection())
            else:
                self.logger.error(
                    "🚨 MQTT recovery failed permanently - max attempts reached"
                )

    async def _destroy_mqtt_client(self) -> None:
        """Completely destroy the existing MQTT client."""
        if not self.mqtt_client:
            return

        self.logger.debug("Destroying old MQTT client")

        try:
            # Stop the loop if it's running
            if hasattr(self.mqtt_client, "_loop_started"):
                self.mqtt_client.loop_stop()
                delattr(self.mqtt_client, "_loop_started")

            # Force disconnect
            if self.mqtt_client.is_connected():
                self.mqtt_client.disconnect()

            # Remove callbacks to prevent issues
            self.mqtt_client.on_connect = None
            self.mqtt_client.on_disconnect = None
            self.mqtt_client.on_message = None
            self.mqtt_client.on_publish = None
            self.mqtt_client.on_log = None

        except Exception as e:
            self.logger.debug(f"Error during MQTT client destruction: {e}")
        finally:
            # Always clear the reference
            self.mqtt_client = None
            self._mqtt_connected = False

    async def _create_fresh_mqtt_client(self) -> None:
        """Create a completely fresh MQTT client and establish connection."""
        self.logger.info("Creating fresh MQTT client")

        # Generate a new unique client ID
        client_id = f"meshcore-mqtt-{uuid.uuid4().hex[:8]}"
        self.logger.debug(f"Using new MQTT client ID: {client_id}")

        # Create brand new client
        self.mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            clean_session=True,  # Always use clean session for reconnections
            reconnect_on_failure=False,  # We handle reconnection ourselves
        )

        # Set up callbacks
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect  # type: ignore
        self.mqtt_client.on_message = self._on_mqtt_message
        self.mqtt_client.on_publish = self._on_mqtt_publish
        self.mqtt_client.on_log = self._on_mqtt_log

        # Set authentication if provided
        if self.config.mqtt.username and self.config.mqtt.password:
            self.mqtt_client.username_pw_set(
                self.config.mqtt.username, self.config.mqtt.password
            )

        # Set connection parameters
        self.mqtt_client.keepalive = 60
        self.mqtt_client.max_inflight_messages_set(1)
        self.mqtt_client.max_queued_messages_set(100)

        # Connect with timeout
        self.logger.debug(
            f"Connecting to MQTT broker "
            f"{self.config.mqtt.broker}:{self.config.mqtt.port}"
        )

        # Use executor to avoid blocking the event loop
        if self.mqtt_client:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.mqtt_client.connect(  # type: ignore
                    self.config.mqtt.broker, self.config.mqtt.port, 60
                ),
            )

        # Start the client loop
        self.mqtt_client.loop_start()

        # Wait a moment for connection to establish
        await asyncio.sleep(2)

        # Verify connection was successful
        if not self.mqtt_client.is_connected():
            raise RuntimeError("MQTT client failed to connect")

        self.logger.info("✅ Fresh MQTT client connected successfully")

    async def _recover_meshcore_connection(self) -> None:
        """Attempt to recover MeshCore connection."""
        if self._meshcore_reconnect_attempts >= self._max_reconnect_attempts:
            self.logger.error("Max MeshCore reconnection attempts reached")
            return

        self._meshcore_reconnect_attempts += 1
        self.logger.warning(
            f"Starting MeshCore recovery (attempt "
            f"{self._meshcore_reconnect_attempts}/{self._max_reconnect_attempts})"
        )

        try:
            # Stop existing connection
            if self.meshcore:
                try:
                    await self.meshcore.stop_auto_message_fetching()
                    await self.meshcore.disconnect()
                except Exception as e:
                    self.logger.debug(f"Error stopping old MeshCore connection: {e}")

            # Wait before attempting reconnection
            delay = min(self._meshcore_reconnect_attempts * 2, 30)
            self.logger.info(f"Waiting {delay}s before MeshCore reconnection")
            await asyncio.sleep(delay)

            # Re-setup MeshCore connection
            await self._setup_meshcore()
            self._meshcore_reconnect_attempts = 0  # Reset on success
            self.logger.info("✅ MeshCore connection recovery successful")

        except Exception as e:
            self.logger.error(
                f"❌ MeshCore recovery attempt "
                f"{self._meshcore_reconnect_attempts} failed: {e}"
            )
            if self._meshcore_reconnect_attempts < self._max_reconnect_attempts:
                retry_delay = min(5 * self._meshcore_reconnect_attempts, 60)
                self.logger.info(f"Scheduling MeshCore retry in {retry_delay}s")
                await asyncio.sleep(retry_delay)
                if self._running:
                    asyncio.create_task(self._recover_meshcore_connection())
            else:
                self.logger.error(
                    "🚨 MeshCore recovery failed permanently - max attempts reached"
                )

    async def _maintain_auto_fetch(self) -> None:
        """Continuously maintain auto-fetch, restarting if it stops."""
        self.logger.info("Starting persistent auto-fetch maintenance")

        while self._running:
            try:
                if (
                    self.meshcore
                    and self._meshcore_connected
                    and not self._auto_fetch_running
                ):
                    self.logger.info("Starting/restarting MeshCore auto-fetch")
                    try:
                        await self.meshcore.start_auto_message_fetching()
                        self._auto_fetch_running = True
                        self._last_meshcore_activity = time.time()
                    except Exception as e:
                        self.logger.error(f"Failed to start auto-fetch: {e}")
                        self._auto_fetch_running = False

                # Check if auto-fetch is still running every minute
                await asyncio.sleep(60)

            except Exception as e:
                self.logger.error(f"Error in auto-fetch maintenance: {e}")
                await asyncio.sleep(60)

    def _on_mqtt_message(
        self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        """Handle incoming MQTT messages."""
        try:
            topic_parts = message.topic.split("/")
            if len(topic_parts) >= 3 and topic_parts[1] == "command":
                command_type = topic_parts[2]
                payload = message.payload.decode("utf-8")

                self.logger.info(f"Received MQTT command: {command_type} = {payload}")

                # Forward command to MeshCore device
                asyncio.create_task(
                    self._forward_mqtt_to_meshcore(command_type, payload)
                )

        except Exception as e:
            self.logger.error(f"Error processing MQTT message: {e}")

    def _on_mqtt_publish(
        self,
        client: mqtt.Client,
        userdata: Any,
        mid: int,
        reason_codes: Any = None,
        properties: Any = None,
    ) -> None:
        """Handle MQTT publish confirmation."""
        self.logger.debug(f"MQTT message published: {mid}")

    def _on_mqtt_log(
        self, client: mqtt.Client, userdata: Any, level: int, buf: str
    ) -> None:
        """Handle MQTT logging."""
        # Map MQTT log levels to Python logging levels
        if level == mqtt.MQTT_LOG_DEBUG:
            self.logger.debug(f"MQTT: {buf}")
        elif level == mqtt.MQTT_LOG_INFO:
            self.logger.info(f"MQTT: {buf}")
        elif level == mqtt.MQTT_LOG_NOTICE:
            self.logger.info(f"MQTT: {buf}")
        elif level == mqtt.MQTT_LOG_WARNING:
            self.logger.warning(f"MQTT: {buf}")
        elif level == mqtt.MQTT_LOG_ERR:
            self.logger.error(f"MQTT: {buf}")
        else:
            self.logger.debug(f"MQTT ({level}): {buf}")

    def _serialize_to_json(self, data: Any) -> str:
        """Safely serialize any data to JSON string."""
        try:
            # Handle common data types that should be JSON serializable
            if isinstance(data, (dict, list, str, int, float, bool)) or data is None:
                return json.dumps(data, ensure_ascii=False)

            # Handle objects with custom serialization
            if hasattr(data, "__dict__"):
                # Convert object to dict, excluding private attributes
                obj_dict = {
                    key: value
                    for key, value in data.__dict__.items()
                    if not key.startswith("_")
                }
                # Only use this if we actually have some public attributes
                if obj_dict:
                    return json.dumps(obj_dict, ensure_ascii=False, default=str)

            # Handle other iterable types
            if hasattr(data, "__iter__") and not isinstance(data, (str, bytes)):
                try:
                    return json.dumps(list(data), ensure_ascii=False, default=str)
                except (TypeError, ValueError):
                    pass

            # Fallback: create a structured JSON object with metadata
            return json.dumps(
                {
                    "type": type(data).__name__,
                    "value": str(data),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
            )

        except Exception as e:
            self.logger.warning(f"Failed to serialize data to JSON: {e}")
            # Ultimate fallback: create error JSON object
            return json.dumps(
                {
                    "error": f"Serialization failed: {str(e)}",
                    "raw_value": str(data)[
                        :1000
                    ],  # Limit length to prevent huge messages
                    "type": type(data).__name__,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
            )

    def _safe_mqtt_publish(
        self,
        topic: str,
        payload: str,
        qos: Optional[int] = None,
        retain: Optional[bool] = None,
    ) -> bool:
        """Safely publish to MQTT with error handling and reconnection."""
        if not self.mqtt_client:
            self.logger.error("MQTT client not initialized")
            return False

        try:
            # Check if client is connected
            if not self.mqtt_client.is_connected():
                self.logger.warning(
                    f"MQTT client not connected, skipping publish to {topic}"
                )
                # Trigger reconnection if bridge is still running
                if self._running:
                    self.logger.debug(
                        "Triggering MQTT reconnection from publish method"
                    )
                    asyncio.create_task(self._recover_mqtt_connection())
                return False

            qos = qos if qos is not None else self.config.mqtt.qos
            retain = retain if retain is not None else self.config.mqtt.retain

            # Add debug logging for message details
            self.logger.debug(
                f"Publishing to MQTT: topic={topic}, qos={qos}, retain={retain}, "
                f"payload_length={len(payload)}"
            )

            result = self.mqtt_client.publish(topic, payload, qos=qos, retain=retain)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.info(f"Successfully published to MQTT topic: {topic}")
                # Update MQTT activity timestamp
                self._last_mqtt_activity = time.time()
                # Wait for message to be sent if QoS > 0
                if qos > 0:
                    result.wait_for_publish(timeout=5.0)
                return True
            elif result.rc == mqtt.MQTT_ERR_NO_CONN:
                self.logger.warning(f"MQTT not connected while publishing to {topic}")
                # Trigger reconnection if bridge is still running
                if self._running:
                    asyncio.create_task(self._recover_mqtt_connection())
                return False
            else:
                self.logger.error(
                    f"Failed to publish to MQTT topic {topic}: "
                    f"{mqtt.error_string(result.rc)} ({result.rc})"
                )
                return False

        except (ConnectionError, OSError, BrokenPipeError) as e:
            self.logger.error(f"Connection error during MQTT publish to {topic}: {e}")
            # Trigger reconnection for connection-related errors
            if self._running:
                self.logger.info("Triggering MQTT reconnection due to connection error")
                asyncio.create_task(self._recover_mqtt_connection())
            return False
        except Exception as e:
            self.logger.error(
                f"Unexpected exception during MQTT publish to {topic}: {e}"
            )
            return False

    async def _forward_mqtt_to_meshcore(self, command_type: str, payload: str) -> None:
        """Forward MQTT command to MeshCore device."""
        if not self.meshcore:
            self.logger.error("MeshCore not initialized")
            return

        try:
            # Parse command payload
            if payload.startswith("{"):
                # JSON payload
                command_data = json.loads(payload)
            else:
                # Plain text payload
                command_data = {"data": payload}

            # Forward to MeshCore (implementation depends on MeshCore API)
            self.logger.info(
                f"Forwarding command to MeshCore: {command_type} -> {command_data}"
            )

            # TODO: Implement actual MeshCore command forwarding based on API

        except Exception as e:
            self.logger.error(f"Error forwarding MQTT command to MeshCore: {e}")

    async def _on_meshcore_message(self, event_data: Any) -> None:
        """Handle messages from MeshCore device."""
        try:
            # Update activity timestamp
            self._last_meshcore_activity = time.time()

            # Convert MeshCore message to MQTT topic and payload
            topic = f"{self.config.mqtt.topic_prefix}/message"
            payload = self._serialize_to_json(event_data)

            # Publish to MQTT using safe method
            self.logger.info(f"Processing MeshCore message for MQTT topic: {topic}")
            if self._safe_mqtt_publish(topic, payload):
                self.logger.info(f"✓ Published MeshCore message to MQTT: {topic}")
            else:
                self.logger.error(
                    f"✗ Failed to publish MeshCore message to MQTT: {topic}"
                )

        except Exception as e:
            self.logger.error(f"Error processing MeshCore message: {e}")

    async def _on_meshcore_connected(self, event_data: Any) -> None:
        """Handle MeshCore connection events."""
        self.logger.info("MeshCore device connected")
        self._meshcore_connected = True
        self._last_meshcore_activity = time.time()

        status_topic = f"{self.config.mqtt.topic_prefix}/status"
        self._safe_mqtt_publish(status_topic, "connected", retain=True)

    async def _on_meshcore_disconnected(self, event_data: Any) -> None:
        """Handle MeshCore disconnection events."""
        self.logger.warning("MeshCore device disconnected")
        self._meshcore_connected = False
        self._auto_fetch_running = False

        status_topic = f"{self.config.mqtt.topic_prefix}/status"
        self._safe_mqtt_publish(status_topic, "disconnected", retain=True)

    async def _on_meshcore_login_success(self, event_data: Any) -> None:
        """Handle MeshCore login success."""
        self.logger.info("MeshCore login successful")
        print("LOGIN SUCCESS:", event_data)

        status_topic = f"{self.config.mqtt.topic_prefix}/login"
        self._safe_mqtt_publish(status_topic, "success", retain=True)

    async def _on_meshcore_login_failed(self, event_data: Any) -> None:
        """Handle MeshCore login failure."""
        self.logger.error("MeshCore login failed")
        print("LOGIN FAILED:", event_data)

        status_topic = f"{self.config.mqtt.topic_prefix}/login"
        self._safe_mqtt_publish(status_topic, "failed", retain=True)

    async def _on_meshcore_messages_waiting(self, event_data: Any) -> None:
        """Handle messages waiting events."""
        self.logger.debug("Messages waiting on MeshCore device")
        print("MESSAGES WAITING:", event_data)

    async def _on_meshcore_device_info(self, event_data: Any) -> None:
        """Handle device info events."""
        self.logger.info("Received MeshCore device info")
        print("DEVICE INFO:", event_data)

        topic = f"{self.config.mqtt.topic_prefix}/device_info"
        payload = self._serialize_to_json(event_data)
        self._safe_mqtt_publish(topic, payload, retain=True)

    async def _on_meshcore_battery(self, event_data: Any) -> None:
        """Handle battery info events."""
        self.logger.debug("Received MeshCore battery info")
        print("BATTERY INFO:", event_data)

        topic = f"{self.config.mqtt.topic_prefix}/battery"
        payload = self._serialize_to_json(event_data)
        self._safe_mqtt_publish(topic, payload)

    async def _on_meshcore_new_contact(self, event_data: Any) -> None:
        """Handle new contact events."""
        self.logger.info("New MeshCore contact discovered")
        print("NEW CONTACT:", event_data)

        topic = f"{self.config.mqtt.topic_prefix}/new_contact"
        payload = self._serialize_to_json(event_data)
        self._safe_mqtt_publish(topic, payload)

    async def _on_meshcore_advertisement(self, event_data: Any) -> None:
        """Handle device advertisement events."""
        self.logger.debug("Received MeshCore device advertisement")
        print("ADVERTISEMENT:", event_data)

        topic = f"{self.config.mqtt.topic_prefix}/advertisement"
        payload = self._serialize_to_json(event_data)
        self._safe_mqtt_publish(topic, payload)

    async def _on_meshcore_no_more_msgs(self, event_data: Any) -> None:
        """Handle NO_MORE_MSGS events - mark auto-fetch as stopped."""
        self.logger.info(f"Received NO_MORE_MSGS event: {event_data}")
        self.logger.info(
            "Auto-fetch has stopped - persistent maintenance will restart it"
        )

        # Mark auto-fetch as stopped so the maintenance task will restart it
        self._auto_fetch_running = False

        # Update activity timestamp
        self._last_meshcore_activity = time.time()

    async def _on_meshcore_debug_event(self, event_data: Any) -> None:
        """Handle any other MeshCore events for debugging."""
        # Try to determine which event this is by inspecting the event_data
        event_info = f"type: {type(event_data)}, data: {event_data}"
        self.logger.debug(f"MeshCore debug event: {event_info}")
        print(f"DEBUG EVENT: {event_info}")

        topic = f"{self.config.mqtt.topic_prefix}/debug_event"
        payload = self._serialize_to_json(event_data)
        self._safe_mqtt_publish(topic, payload, retain=False)
