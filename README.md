# Indigo-Konnected
Indigo plugin for Konnected security panel devices

## Overview

This plugin enables integration between the [Indigo Home Automation](http://www.indigodomo.com) system and [Konnected](https://konnected.io) security panel devices. Konnected devices allow you to convert traditional wired security systems into smart, connected systems.

## Features

- **Device Discovery**: Automatically discover Konnected devices on your network
- **Sensor Support**: Monitor door/window sensors, motion detectors, smoke alarms, CO detectors, water leak sensors, and more
- **Output Control**: Control sirens, strobe lights, and other relay-based outputs
- **GDO Blaq Support**: Full support for Konnected GDO Blaq garage door controllers
- **Real-time Updates**: Monitor sensor states with configurable polling intervals
- **Multiple Panels**: Support for multiple Konnected panels and GDO devices on the same network

## Supported Device Types

### Konnected Panel
The main controller device that communicates with the Konnected hardware.

**Configuration:**
- IP Address: The network IP address of your Konnected device
- Port: Network port (typically 80)
- Authentication Token: Optional security token
- Polling Frequency: How often to check for sensor updates (5 seconds to 5 minutes)

### Konnected Sensor
Individual sensors connected to the Konnected panel.

**Supported Sensor Types:**
- Contact Sensor (door/window)
- Motion Sensor
- Smoke Detector
- CO Detector
- Water Leak Sensor
- Generic Sensor

**Configuration:**
- Panel Device: Which Konnected panel this sensor is connected to
- Zone Number: The zone/pin number on the panel (1-6 or 1-12 depending on model)
- Sensor Type: The type of sensor for proper identification
- Invert Logic: Option to invert sensor logic (normally closed vs normally open)

### Konnected Output
Relay outputs for controlling external devices.

**Supported Output Types:**
- Siren/Alarm
- Strobe Light
- Generic Relay

**Configuration:**
- Panel Device: Which Konnected panel this output is connected to
- Zone Number: The zone/pin number for the output (typically 7-12)
- Output Type: The type of output device

### Konnected GDO Blaq
Smart garage door controllers with advanced features.

**Supported Features:**
- Garage door control (open/close/stop/position)
- Garage light control
- Motion detection (if equipped)
- Obstruction sensor monitoring
- Remote control lock/unlock
- Real-time door position tracking
- **EventSource (SSE) monitoring**: Real-time status updates without polling for improved responsiveness and reduced network traffic

**Configuration:**
- IP Address: The network IP address of your GDO Blaq device
- Port: Network port (typically 80)
- Username/Password: Optional authentication credentials
- **Use EventSource (SSE)**: Enable Server-Sent Events for real-time monitoring (recommended)
- Polling Frequency: Fallback polling interval when SSE is disabled or unavailable (5-60 seconds)

## Installation

1. Download the plugin from the [Releases](https://github.com/FlyingDiver/Indigo-Konnected/releases) page
2. Double-click the downloaded .indigoplugin file to install
3. Enable the plugin in Indigo's Plugin Settings

## Quick Start

1. **Discover Devices**: Use the "Discover Konnected Devices" menu item to find devices on your network
2. **Create Panel or GDO**: Create a new "Konnected Panel" device with the discovered IP address, or "Konnected GDO Blaq" for garage door controllers
3. **Add Sensors**: Create "Konnected Sensor" devices for each sensor connected to your panel
4. **Add Outputs**: Create "Konnected Output" devices for any relay outputs you want to control

## Device Setup Guide

### Setting up a Konnected Panel

1. In Indigo, go to Devices → New Device
2. Select "Konnected" from the device type list
3. Choose "Konnected Panel"
4. Configure:
   - **Name**: Give your panel a descriptive name
   - **IP Address**: Enter the IP address found during discovery
   - **Port**: Usually 80 (default)
   - **Auth Token**: Leave blank unless you've configured authentication
   - **Polling Frequency**: Choose how often to check for updates (30 seconds recommended)

### Setting up Sensors

1. Create a new device and select "Konnected Sensor"
2. Configure:
   - **Panel Device**: Select the panel this sensor connects to
   - **Zone Number**: Enter the zone number (check your Konnected web interface)
   - **Sensor Type**: Choose the appropriate type
   - **Invert Logic**: Check if your sensor operates in reverse (normally closed)

### Setting up Outputs

1. Create a new device and select "Konnected Output"
2. Configure:
   - **Panel Device**: Select the panel this output connects to
   - **Zone Number**: Enter the output zone number
   - **Output Type**: Choose the type of output device

### Setting up GDO Blaq Devices

1. Create a new device and select "Konnected GDO Blaq"
2. Configure:
   - **Name**: Give your GDO device a descriptive name
   - **IP Address**: Enter the IP address of your GDO Blaq device
   - **Port**: Usually 80 (default)
   - **Username/Password**: Enter credentials if authentication is enabled
   - **Use EventSource (SSE)**: Leave enabled for real-time updates (recommended)
   - **Polling Frequency**: Fallback polling interval (10 seconds recommended)

## Actions and Controls

### Available Actions

- **Discover Konnected Devices**: Scan the network for Konnected devices
- **Refresh Panel Status**: Immediately update a panel's status
- **Test Panel Connection**: Verify connection to a panel
- **Activate Output**: Turn on an output for a specified duration
- **Open/Close/Stop Garage Door**: Control GDO Blaq garage doors
- **Set Garage Door Position**: Move door to specific position (0-100%)
- **Toggle Garage Light**: Control GDO garage lighting
- **Refresh GDO Status**: Update GDO device status immediately

### Device Controls

- **Sensors**: Automatically update based on physical sensor state
- **Outputs**: Can be turned on/off manually or via triggers/schedules
- **GDO Doors**: Can be opened, closed, stopped, or positioned via actions
- **GDO Lights**: Can be controlled independently of door operation

## Troubleshooting

### Common Issues

1. **Device Not Found**: Ensure your Konnected device is on the same network as your Indigo server
2. **Connection Failed**: Check IP address and ensure the device is powered on
3. **Sensor Not Updating**: Verify zone numbers and check physical connections
4. **Authentication Errors**: Ensure auth token matches your Konnected device configuration
5. **GDO EventSource Issues**: 
   - If SSE connection fails, the plugin automatically falls back to polling
   - Check device logs for "EventSource failed" messages
   - Disable SSE in device configuration if persistent issues occur
   - Verify firewall allows persistent HTTP connections

### Connection Status Indicators

- **Connected (SSE)**: Device is monitored via real-time EventSource connection
- **Connected (Polling)**: Device is monitored via traditional polling
- **Retrying**: Attempting to reconnect after connection failure
- **Disconnected**: Unable to reach device after multiple attempts

### Debug Mode

Enable debug logging in the plugin preferences for detailed troubleshooting information.

## Technical Details

### API Communication

The plugin communicates with Konnected devices using their REST API:
- **Status Endpoint**: `GET /status` - Retrieves sensor states and device info
- **Control Endpoint**: `PUT /device` - Controls relay outputs
- **Discovery**: Uses SSDP (Simple Service Discovery Protocol) for device discovery

**GDO Blaq Communication:**
- **EventSource (SSE)**: Real-time monitoring via Server-Sent Events on endpoints like `/events`, `/stream`
- **REST API**: Fallback polling using endpoints like `/cover/garage_door`, `/light/garage_light`
- **Event Types**: Supports `door`, `light`, `state`, and `message` event types for comprehensive monitoring

### Network Requirements

- Konnected devices must be on the same network as your Indigo server
- UDP port 1900 must be available for SSDP discovery
- HTTP communication on the configured port (default 80)
- **For SSE**: Persistent HTTP connections for EventSource streams

## Support

For issues, feature requests, or contributions:
- GitHub Issues: [https://github.com/FlyingDiver/Indigo-Konnected/issues](https://github.com/FlyingDiver/Indigo-Konnected/issues)
- Indigo Forums: [https://forums.indigodomo.com](https://forums.indigodomo.com)

## License

This plugin is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Version History

### 1.0.0
- Initial release
- Basic device discovery and communication
- Support for sensors and relay outputs
- Configurable polling intervals
- Device actions and menu items
