"""Tests for MQTT command forwarding to MeshCore."""

from unittest.mock import AsyncMock, MagicMock
from typing import Any

import pytest

from meshcore_mqtt.meshcore_client import MeshCoreClientManager
from meshcore_mqtt.config import Config, ConnectionType, MeshCoreConfig, MQTTConfig


@pytest.fixture
def test_config() -> Config:
    """Create a test configuration."""
    return Config(
        mqtt=MQTTConfig(broker="localhost"),
        meshcore=MeshCoreConfig(
            connection_type=ConnectionType.TCP,
            address="127.0.0.1",
            port=12345,
        ),
    )


@pytest.fixture
def meshcore_manager(test_config: Config) -> MeshCoreClientManager:
    """Create a MeshCore manager instance for testing."""
    return MeshCoreClientManager(test_config)


class TestCommandForwarding:
    """Test MQTT command forwarding to MeshCore."""

    async def test_send_msg_command(self, meshcore_manager: MeshCoreClientManager) -> None:
        """Test send_msg command forwarding."""
        # Setup mock MeshCore instance
        mock_meshcore = MagicMock()
        mock_meshcore.commands = MagicMock()
        mock_meshcore.commands.send_msg = AsyncMock()
        meshcore_manager.meshcore = mock_meshcore

        # Test send_msg command
        command_data = {"destination": "Alice", "message": "Hello!"}
        await meshcore_manager.send_command("send_msg", command_data)

        # Verify the command was called
        mock_meshcore.commands.send_msg.assert_called_once_with("Alice", "Hello!")

    async def test_send_channel_msg_command(self, meshcore_manager: MeshCoreClientManager) -> None:
        """Test send_channel_msg command forwarding."""
        # Setup mock MeshCore instance
        mock_meshcore = MagicMock()
        mock_meshcore.commands = MagicMock()
        mock_meshcore.commands.send_channel_msg = AsyncMock()
        meshcore_manager.meshcore = mock_meshcore

        # Test send_channel_msg command
        command_data = {"channel": "general", "message": "Hello group!"}
        await meshcore_manager.send_command("send_channel_msg", command_data)

        # Verify the command was called
        mock_meshcore.commands.send_channel_msg.assert_called_once_with("general", "Hello group!")

    async def test_device_query_command(self, meshcore_manager: MeshCoreClientManager) -> None:
        """Test device_query command forwarding."""
        # Setup mock MeshCore instance
        mock_meshcore = MagicMock()
        mock_meshcore.commands = MagicMock()
        mock_meshcore.commands.send_device_query = AsyncMock()
        meshcore_manager.meshcore = mock_meshcore

        # Test device_query command
        await meshcore_manager.send_command("device_query", {})

        # Verify the command was called
        mock_meshcore.commands.send_device_query.assert_called_once()

    async def test_ping_command(self, meshcore_manager: MeshCoreClientManager) -> None:
        """Test ping command forwarding."""
        # Setup mock MeshCore instance
        mock_meshcore = MagicMock()
        mock_meshcore.commands = MagicMock()
        mock_meshcore.commands.ping = AsyncMock()
        meshcore_manager.meshcore = mock_meshcore

        # Test ping command
        command_data = {"destination": "node123"}
        await meshcore_manager.send_command("ping", command_data)

        # Verify the command was called
        mock_meshcore.commands.ping.assert_called_once_with("node123")

    async def test_set_name_command(self, meshcore_manager: MeshCoreClientManager) -> None:
        """Test set_name command forwarding."""
        # Setup mock MeshCore instance
        mock_meshcore = MagicMock()
        mock_meshcore.commands = MagicMock()
        mock_meshcore.commands.set_name = AsyncMock()
        meshcore_manager.meshcore = mock_meshcore

        # Test set_name command
        command_data = {"name": "MyDevice"}
        await meshcore_manager.send_command("set_name", command_data)

        # Verify the command was called
        mock_meshcore.commands.set_name.assert_called_once_with("MyDevice")

    async def test_missing_required_fields(self, meshcore_manager: MeshCoreClientManager) -> None:
        """Test command validation for missing required fields."""
        # Setup mock MeshCore instance
        mock_meshcore = MagicMock()
        mock_meshcore.commands = MagicMock()
        mock_meshcore.commands.send_msg = AsyncMock()
        meshcore_manager.meshcore = mock_meshcore

        # Test send_msg without required fields
        command_data = {"message": "Hello!"}  # Missing destination
        await meshcore_manager.send_command("send_msg", command_data)

        # Verify the command was NOT called due to validation
        mock_meshcore.commands.send_msg.assert_not_called()

    async def test_unknown_command_type(self, meshcore_manager: MeshCoreClientManager) -> None:
        """Test handling of unknown command types."""
        # Setup mock MeshCore instance
        mock_meshcore = MagicMock()
        meshcore_manager.meshcore = mock_meshcore

        # Test unknown command
        await meshcore_manager.send_command("unknown_command", {})

        # Should not raise an exception, just log a warning

    async def test_no_meshcore_instance(self, meshcore_manager: MeshCoreClientManager) -> None:
        """Test command handling when MeshCore instance is None."""
        # Ensure meshcore is None
        meshcore_manager.meshcore = None

        # Test command - should not raise exception
        await meshcore_manager.send_command("send_msg", {"destination": "test", "message": "test"})

    async def test_command_error_handling(self, meshcore_manager: MeshCoreClientManager) -> None:
        """Test error handling when MeshCore command fails."""
        # Setup mock MeshCore instance that raises an exception
        mock_meshcore = MagicMock()
        mock_meshcore.commands = MagicMock()
        mock_meshcore.commands.send_msg = AsyncMock(side_effect=Exception("Test error"))
        meshcore_manager.meshcore = mock_meshcore

        # Test command - should not raise exception, just log error
        command_data = {"destination": "Alice", "message": "Hello!"}
        await meshcore_manager.send_command("send_msg", command_data)

        # Verify the command was attempted
        mock_meshcore.commands.send_msg.assert_called_once_with("Alice", "Hello!")

    async def test_activity_update_on_successful_command(self, meshcore_manager: MeshCoreClientManager) -> None:
        """Test that activity timestamp is updated on successful commands."""
        # Setup mock MeshCore instance
        mock_meshcore = MagicMock()
        mock_meshcore.commands = MagicMock()
        mock_meshcore.commands.advertise = AsyncMock(return_value=None)
        meshcore_manager.meshcore = mock_meshcore
        
        # Mock the update_activity method
        meshcore_manager.update_activity = MagicMock()

        # Test advertise command (no result object)
        await meshcore_manager.send_command("advertise", {})

        # Verify activity was updated
        meshcore_manager.update_activity.assert_called_once()