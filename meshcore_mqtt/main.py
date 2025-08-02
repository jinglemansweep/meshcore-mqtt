"""Main entry point for MeshCore MQTT Bridge."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import click

from .config import Config, ConnectionType


def setup_logging(level: str) -> None:
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


@click.command()
@click.option(
    "--config-file",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file (JSON or YAML)",
)
@click.option(
    "--mqtt-broker",
    help="MQTT broker address",
)
@click.option(
    "--mqtt-port",
    type=int,
    default=1883,
    help="MQTT broker port (default: 1883)",
)
@click.option(
    "--mqtt-username",
    help="MQTT username",
)
@click.option(
    "--mqtt-password",
    help="MQTT password",
)
@click.option(
    "--mqtt-topic-prefix",
    default="meshcore",
    help="MQTT topic prefix (default: meshcore)",
)
@click.option(
    "--mqtt-qos",
    type=click.IntRange(0, 2),
    default=0,
    help="MQTT QoS level (default: 0)",
)
@click.option(
    "--mqtt-retain/--no-mqtt-retain",
    default=False,
    help="Enable MQTT message retention (default: disabled)",
)
@click.option(
    "--meshcore-connection",
    type=click.Choice([conn.value for conn in ConnectionType]),
    help="MeshCore connection type",
)
@click.option(
    "--meshcore-address",
    help="MeshCore device address",
)
@click.option(
    "--meshcore-port",
    type=int,
    help="MeshCore device port (for TCP connections)",
)
@click.option(
    "--meshcore-baudrate",
    type=int,
    default=115200,
    help="MeshCore baudrate for serial connections (default: 115200)",
)
@click.option(
    "--meshcore-timeout",
    type=int,
    default=5,
    help="MeshCore operation timeout in seconds (default: 5)",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    help="Logging level (default: INFO)",
)
@click.option(
    "--env",
    is_flag=True,
    help="Load configuration from environment variables",
)
def main(
    config_file: Optional[Path],
    mqtt_broker: Optional[str],
    mqtt_port: int,
    mqtt_username: Optional[str],
    mqtt_password: Optional[str],
    mqtt_topic_prefix: str,
    mqtt_qos: int,
    mqtt_retain: bool,
    meshcore_connection: Optional[str],
    meshcore_address: Optional[str],
    meshcore_port: Optional[int],
    meshcore_baudrate: int,
    meshcore_timeout: int,
    log_level: str,
    env: bool,
) -> None:
    """MeshCore to MQTT Bridge.

    Bridge messages between MeshCore devices and MQTT brokers.
    Configuration can be provided via command-line arguments,
    configuration file, or environment variables.
    """
    try:
        # Load configuration in order of precedence:
        # 1. Command line arguments (highest priority)
        # 2. Configuration file
        # 3. Environment variables (lowest priority)

        if config_file:
            config = Config.from_file(config_file)
        elif env:
            config = Config.from_env()
        else:
            # Build config from command line arguments
            if not mqtt_broker or not meshcore_connection or not meshcore_address:
                click.echo(
                    "Error: --mqtt-broker, --meshcore-connection, and "
                    "--meshcore-address are required when not using a config file",
                    err=True,
                )
                sys.exit(1)

            from .config import MQTTConfig, MeshCoreConfig

            mqtt_config = MQTTConfig(
                broker=mqtt_broker,
                port=mqtt_port,
                username=mqtt_username,
                password=mqtt_password,
                topic_prefix=mqtt_topic_prefix,
                qos=mqtt_qos,
                retain=mqtt_retain,
            )

            meshcore_config = MeshCoreConfig(
                connection_type=ConnectionType(meshcore_connection),
                address=meshcore_address,
                port=meshcore_port,
                baudrate=meshcore_baudrate,
                timeout=meshcore_timeout,
            )

            config = Config(
                mqtt=mqtt_config,
                meshcore=meshcore_config,
                log_level=log_level,
            )

        # Override config with any provided command line arguments
        if mqtt_broker:
            config.mqtt.broker = mqtt_broker
        if mqtt_username:
            config.mqtt.username = mqtt_username
        if mqtt_password:
            config.mqtt.password = mqtt_password
        if meshcore_connection:
            config.meshcore.connection_type = ConnectionType(meshcore_connection)
        if meshcore_address:
            config.meshcore.address = meshcore_address
        if meshcore_port:
            config.meshcore.port = meshcore_port
        if meshcore_baudrate != 115200:  # Only override if different from default
            config.meshcore.baudrate = meshcore_baudrate

        # Set up logging
        setup_logging(config.log_level)
        logger = logging.getLogger(__name__)

        logger.info("Starting MeshCore MQTT Bridge")
        logger.info(f"MQTT Broker: {config.mqtt.broker}:{config.mqtt.port}")
        logger.info(
            f"MeshCore: {config.meshcore.connection_type.value}://"
            f"{config.meshcore.address}"
        )

        # Run the bridge application
        asyncio.run(run_bridge(config))

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


async def run_bridge(config: Config) -> None:
    """Run the MeshCore MQTT bridge."""
    from .bridge import MeshCoreMQTTBridge

    logger = logging.getLogger(__name__)
    bridge = MeshCoreMQTTBridge(config)

    try:
        # Start the bridge
        await bridge.start()

        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Bridge interrupted by user")
    except Exception as e:
        logger.error(f"Bridge error: {e}")
        raise
    finally:
        # Clean shutdown
        await bridge.stop()


if __name__ == "__main__":
    main()
