"""Core bridge implementation between MeshCore and MQTT."""

import asyncio
import json
import logging
from typing import Any

from .config import Config
from .meshcore_client import MeshCoreClientManager
from .mqtt_client import MQTTClientManager


class MeshCoreMQTTBridge:
    """Bridge between MeshCore devices and MQTT brokers."""

    def __init__(self, config: Config) -> None:
        """Initialize the bridge with configuration."""
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Client managers
        self.mqtt_manager = MQTTClientManager(config)
        self.meshcore_manager = MeshCoreClientManager(config)

        # State management
        self._running = False
        self._tasks: list[asyncio.Task[Any]] = []

    async def start(self) -> None:
        """Start the bridge service."""
        if self._running:
            self.logger.warning("Bridge is already running")
            return

        self.logger.info("Starting MeshCore MQTT Bridge")

        try:
            # Start MQTT client
            await self.mqtt_manager.start()

            # Set up event handlers
            self._setup_event_handlers()

            # Start MeshCore client
            await self.meshcore_manager.start()

            # Start the bridge loops
            self._running = True

            # Start monitoring and maintenance tasks
            monitor_task = asyncio.create_task(self._monitor_connections())
            self._tasks.append(monitor_task)

            autofetch_task = self.meshcore_manager.get_auto_fetch_task()
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

        # Stop client managers
        await self.meshcore_manager.stop()
        await self.mqtt_manager.stop()

        self.logger.info("Bridge stopped")

    def _setup_event_handlers(self) -> None:
        """Set up event handlers between MeshCore and MQTT."""
        self.logger.info("Setting up event handlers")

        # Register MeshCore event handlers
        self.meshcore_manager.register_event_handler(
            "CONTACT_MSG_RECV", self._on_meshcore_message
        )
        self.meshcore_manager.register_event_handler(
            "CHANNEL_MSG_RECV", self._on_meshcore_message
        )
        self.meshcore_manager.register_event_handler(
            "CONNECTED", self._on_meshcore_connected
        )
        self.meshcore_manager.register_event_handler(
            "DISCONNECTED", self._on_meshcore_disconnected
        )
        self.meshcore_manager.register_event_handler(
            "LOGIN_SUCCESS", self._on_meshcore_login_success
        )
        self.meshcore_manager.register_event_handler(
            "LOGIN_FAILED", self._on_meshcore_login_failed
        )
        self.meshcore_manager.register_event_handler(
            "MESSAGES_WAITING", self._on_meshcore_messages_waiting
        )
        self.meshcore_manager.register_event_handler(
            "DEVICE_INFO", self._on_meshcore_device_info
        )
        self.meshcore_manager.register_event_handler(
            "BATTERY", self._on_meshcore_battery
        )
        self.meshcore_manager.register_event_handler(
            "NEW_CONTACT", self._on_meshcore_new_contact
        )
        self.meshcore_manager.register_event_handler(
            "ADVERTISEMENT", self._on_meshcore_advertisement
        )

        # Register MQTT command handler
        self.mqtt_manager.register_command_handler("*", self._forward_mqtt_to_meshcore)

    async def _run_bridge(self) -> None:
        """Run the main bridge loop."""
        self.logger.info("Bridge is now running")

        try:
            # Keep running until stopped
            while self._running:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            self.logger.info("Bridge loop cancelled")
        except Exception as e:
            self.logger.error(f"Error in bridge loop: {e}")
            raise

    async def _monitor_connections(self) -> None:
        """Monitor both MeshCore and MQTT connections and attempt recovery."""
        self.logger.info("Starting connection monitoring")

        while self._running:
            try:
                # Perform health checks on both managers
                mqtt_healthy = await self.mqtt_manager.health_check()
                meshcore_healthy = await self.meshcore_manager.health_check()

                if not mqtt_healthy:
                    self.logger.debug("MQTT connection needs attention")

                if not meshcore_healthy:
                    self.logger.debug("MeshCore connection needs attention")

                # Sleep before next check
                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                self.logger.error(f"Error in connection monitoring: {e}")
                await asyncio.sleep(30)

    def _forward_mqtt_to_meshcore(self, command_type: str, payload: str) -> None:
        """Forward MQTT command to MeshCore device."""
        try:
            # Parse command payload
            if payload.startswith("{"):
                command_data = json.loads(payload)
            else:
                command_data = {"data": payload}

            self.logger.info(
                f"Forwarding command to MeshCore: {command_type} -> {command_data}"
            )

            # Forward to MeshCore manager
            asyncio.create_task(
                self.meshcore_manager.send_command(command_type, command_data)
            )

        except Exception as e:
            self.logger.error(f"Error forwarding MQTT command to MeshCore: {e}")

    def _on_meshcore_message(self, event_data: Any) -> None:
        """Handle messages from MeshCore device."""
        try:
            # Update activity timestamp
            self.meshcore_manager.update_activity()

            # Convert MeshCore message to MQTT topic and payload
            topic = f"{self.config.mqtt.topic_prefix}/message"
            payload = self.meshcore_manager.serialize_to_json(event_data)

            # Publish to MQTT
            self.logger.info(f"Processing MeshCore message for MQTT topic: {topic}")
            if self.mqtt_manager.publish(topic, payload):
                self.logger.info(f"✓ Published MeshCore message to MQTT: {topic}")
            else:
                self.logger.error(
                    f"✗ Failed to publish MeshCore message to MQTT: {topic}"
                )

        except Exception as e:
            self.logger.error(f"Error processing MeshCore message: {e}")

    def _on_meshcore_connected(self, event_data: Any) -> None:
        """Handle MeshCore connection events."""
        self.logger.info("MeshCore device connected")
        self.meshcore_manager.update_activity()

        status_topic = f"{self.config.mqtt.topic_prefix}/status"
        self.mqtt_manager.publish(status_topic, "connected", retain=True)

    def _on_meshcore_disconnected(self, event_data: Any) -> None:
        """Handle MeshCore disconnection events."""
        self.logger.warning("MeshCore device disconnected")

        status_topic = f"{self.config.mqtt.topic_prefix}/status"
        self.mqtt_manager.publish(status_topic, "disconnected", retain=True)

    def _on_meshcore_login_success(self, event_data: Any) -> None:
        """Handle MeshCore login success."""
        self.logger.info("MeshCore login successful")
        print("LOGIN SUCCESS:", event_data)

        status_topic = f"{self.config.mqtt.topic_prefix}/login"
        self.mqtt_manager.publish(status_topic, "success", retain=True)

    def _on_meshcore_login_failed(self, event_data: Any) -> None:
        """Handle MeshCore login failure."""
        self.logger.error("MeshCore login failed")
        print("LOGIN FAILED:", event_data)

        status_topic = f"{self.config.mqtt.topic_prefix}/login"
        self.mqtt_manager.publish(status_topic, "failed", retain=True)

    def _on_meshcore_messages_waiting(self, event_data: Any) -> None:
        """Handle messages waiting events."""
        self.logger.debug("Messages waiting on MeshCore device")
        print("MESSAGES WAITING:", event_data)

    def _on_meshcore_device_info(self, event_data: Any) -> None:
        """Handle device info events."""
        self.logger.info("Received MeshCore device info")
        print("DEVICE INFO:", event_data)

        topic = f"{self.config.mqtt.topic_prefix}/device_info"
        payload = self.meshcore_manager.serialize_to_json(event_data)
        self.mqtt_manager.publish(topic, payload, retain=True)

    def _on_meshcore_battery(self, event_data: Any) -> None:
        """Handle battery info events."""
        self.logger.debug("Received MeshCore battery info")
        print("BATTERY INFO:", event_data)

        topic = f"{self.config.mqtt.topic_prefix}/battery"
        payload = self.meshcore_manager.serialize_to_json(event_data)
        self.mqtt_manager.publish(topic, payload)

    def _on_meshcore_new_contact(self, event_data: Any) -> None:
        """Handle new contact events."""
        self.logger.info("New MeshCore contact discovered")
        print("NEW CONTACT:", event_data)

        topic = f"{self.config.mqtt.topic_prefix}/new_contact"
        payload = self.meshcore_manager.serialize_to_json(event_data)
        self.mqtt_manager.publish(topic, payload)

    def _on_meshcore_advertisement(self, event_data: Any) -> None:
        """Handle device advertisement events."""
        self.logger.debug("Received MeshCore device advertisement")
        print("ADVERTISEMENT:", event_data)

        topic = f"{self.config.mqtt.topic_prefix}/advertisement"
        payload = self.meshcore_manager.serialize_to_json(event_data)
        self.mqtt_manager.publish(topic, payload)

    # Compatibility methods for tests
    @property
    def meshcore(self) -> Any:
        """Compatibility property for tests."""
        return self.meshcore_manager.meshcore

    @property
    def connection_manager(self) -> Any:
        """Compatibility property for tests."""
        return self.meshcore_manager.connection_manager

    @property
    def mqtt_client(self) -> Any:
        """Compatibility property for tests."""
        return self.mqtt_manager.client

    def _serialize_to_json(self, data: Any) -> str:
        """Compatibility method for tests."""
        return self.meshcore_manager.serialize_to_json(data)

    async def _setup_mqtt(self) -> None:
        """Compatibility method for tests."""
        await self.mqtt_manager.start()
