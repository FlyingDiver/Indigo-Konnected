# Changelog

All notable changes to the Konnected Plugin for Indigo will be documented in this file.

## [1.0.0] - 2025-01-XX

### Added
- Initial release of Konnected Plugin for Indigo
- Device discovery via SSDP protocol to automatically find Konnected panels on the network
- Support for Konnected Panel devices with configurable IP, port, and authentication
- Support for Konnected Sensor devices with multiple sensor types:
  - Contact sensors (door/window)
  - Motion detectors
  - Smoke detectors
  - CO detectors
  - Water leak sensors
  - Generic sensors
- Support for Konnected Output devices for controlling:
  - Sirens/alarms
  - Strobe lights
  - Generic relays
- Real-time sensor monitoring with configurable polling intervals (5 seconds to 5 minutes)
- Device validation and error handling
- Automatic retry logic for failed connections
- Plugin preferences for timeout and behavior configuration
- Device actions for:
  - Device discovery
  - Panel status refresh
  - Connection testing
  - Output activation with duration control
- Plugin menu items for easy access to common functions
- Comprehensive documentation and configuration examples
- Error recovery with automatic connection retry
- Input validation for all device configurations
- Debug logging support for troubleshooting

### Plugin Architecture
- Clean separation between panel, sensor, and output device types
- Thread-based monitoring for each panel device
- RESTful API communication with Konnected devices
- Graceful error handling and connection recovery
- Configurable timeouts and retry behavior

### Documentation
- Complete setup guide with examples
- Troubleshooting section
- Common configuration patterns
- Zone assignment guidelines
- Sensor type recommendations