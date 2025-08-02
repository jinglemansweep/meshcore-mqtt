"""Configuration system for MeshCore MQTT Bridge."""

import json
import os
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union

import yaml
from pydantic import BaseModel, Field, field_validator


class ConnectionType(str, Enum):
    """Supported MeshCore connection types."""

    SERIAL = "serial"
    BLE = "ble"
    TCP = "tcp"


class MQTTConfig(BaseModel):
    """MQTT broker configuration."""

    broker: str = Field(..., description="MQTT broker address")
    port: int = Field(default=1883, description="MQTT broker port")
    username: Optional[str] = Field(default=None, description="MQTT username")
    password: Optional[str] = Field(default=None, description="MQTT password")
    topic_prefix: str = Field(default="meshcore", description="MQTT topic prefix")
    qos: int = Field(default=0, ge=0, le=2, description="Quality of Service level")
    retain: bool = Field(default=False, description="Message retention flag")

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate MQTT port number."""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


class MeshCoreConfig(BaseModel):
    """MeshCore device configuration."""

    connection_type: ConnectionType = Field(..., description="Connection type")
    address: str = Field(..., description="Device address")
    port: Optional[int] = Field(default=None, description="Device port for TCP")
    baudrate: int = Field(default=115200, description="Baudrate for serial connections")
    timeout: int = Field(default=5, gt=0, description="Operation timeout in seconds")

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: Optional[int], info: Any) -> Optional[int]:
        """Validate port is provided for TCP connections."""
        # Get connection_type from the validation context
        connection_type = info.data.get("connection_type") if info.data else None

        # Set default port for TCP if None provided
        if connection_type == ConnectionType.TCP and v is None:
            v = 12345

        if v is not None and not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")

        return v


class Config(BaseModel):
    """Main application configuration."""

    mqtt: MQTTConfig
    meshcore: MeshCoreConfig
    log_level: str = Field(default="INFO", description="Logging level")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()

    @classmethod
    def from_file(cls, config_path: Union[str, Path]) -> "Config":
        """Load configuration from a file (JSON or YAML)."""
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, "r") as f:
            if config_path.suffix.lower() in [".yaml", ".yml"]:
                try:
                    data = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    raise ValueError(f"Invalid YAML configuration: {e}")
            else:
                try:
                    data = json.load(f)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON configuration: {e}")

        return cls(**data)

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        mqtt_config = MQTTConfig(
            broker=os.getenv("MQTT_BROKER", ""),
            port=int(os.getenv("MQTT_PORT", "1883")),
            username=os.getenv("MQTT_USERNAME"),
            password=os.getenv("MQTT_PASSWORD"),
            topic_prefix=os.getenv("MQTT_TOPIC_PREFIX", "meshcore"),
            qos=int(os.getenv("MQTT_QOS", "0")),
            retain=os.getenv("MQTT_RETAIN", "false").lower() == "true",
        )

        meshcore_config = MeshCoreConfig(
            connection_type=ConnectionType(os.getenv("MESHCORE_CONNECTION", "tcp")),
            address=os.getenv("MESHCORE_ADDRESS", ""),
            port=(
                int(os.getenv("MESHCORE_PORT", "12345"))
                if os.getenv("MESHCORE_PORT")
                else None
            ),
            baudrate=int(os.getenv("MESHCORE_BAUDRATE", "115200")),
            timeout=int(os.getenv("MESHCORE_TIMEOUT", "5")),
        )

        return cls(
            mqtt=mqtt_config,
            meshcore=meshcore_config,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
