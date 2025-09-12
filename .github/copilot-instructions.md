# Indigo-Konnected Plugin

This is a Python plugin for Indigo Home Automation that integrates with Konnected security panel devices. The plugin enables communication between Indigo and Konnected hardware for monitoring sensors and controlling outputs.

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Working Effectively

### Prerequisites
- Python 3.12+ is available by default
- `requests` module is pre-installed (version 2.31.0+)
- This is an Indigo plugin, NOT a standalone application

### Core Validation Steps
Run these commands to validate the plugin:
- `cd /home/runner/work/Indigo-Konnected/Indigo-Konnected`
- `python3 test_plugin.py` -- Takes <1 second. Tests core plugin logic.
- `python3 -m py_compile plugin.py` -- Takes <1 second. Validates Python syntax.
- `python3 -m py_compile test_plugin.py` -- Takes <1 second. Validates test syntax.
- `python3 -c "import plugin; print('Plugin import: SUCCESS')"` -- Takes <1 second. Tests import capability.

### XML Configuration Validation
Validate all XML configuration files:
- `python3 -c "import xml.etree.ElementTree as ET; [ET.parse(f) for f in ['Actions.xml', 'Devices.xml', 'MenuItems.xml', 'PluginConfig.xml', 'Info.plist']]; print('All XML files valid')"` -- Takes <1 second.

### Testing and Development
- ALWAYS run `python3 test_plugin.py` after making changes to core plugin logic
- The test script simulates Konnected device responses without requiring actual hardware
- Plugin import works with mock Indigo module for testing outside Indigo environment
- All operations complete in under 1 second - no long timeouts needed

## Plugin Architecture

### Key Files
- `plugin.py` - Main plugin implementation (41KB, ~947 lines)
- `test_plugin.py` - Standalone test script for validation (3.6KB, ~128 lines)
- `Actions.xml` - Defines plugin actions (discovery, refresh, test, activate)
- `Devices.xml` - Defines device types (Panel, Sensor, Output) 
- `MenuItems.xml` - Plugin menu structure
- `PluginConfig.xml` - Plugin preferences and settings
- `Info.plist` - Plugin metadata and version info
- `examples/README.md` - Configuration examples and troubleshooting

### Device Types Supported
1. **Konnected Panel** - Main controller device
2. **Konnected Sensor** - Individual sensors (contact, motion, smoke, CO, leak, generic)  
3. **Konnected Output** - Relay outputs (siren, strobe, generic relay)

### Dependencies
- `requests` - HTTP communication with Konnected devices (pre-installed)
- `json` - JSON parsing for API responses (built-in)
- `socket` - UDP operations for SSDP discovery (built-in)
- `threading` - Background monitoring threads (built-in)
- `indigo` - Indigo API module (only available within Indigo environment)

## Validation Scenarios

### After Making Changes
ALWAYS run these validation steps:
1. `python3 test_plugin.py` - Verify core logic works
2. `python3 -m py_compile plugin.py` - Check syntax
3. `python3 -c "import plugin"` - Test import capability
4. Check XML files if you modified any configuration

### Testing Network Functionality
The plugin uses HTTP requests to communicate with Konnected devices. Test network capabilities:
```bash
python3 -c "import requests; session = requests.Session(); session.timeout = 5; print('Requests module: SUCCESS')"
```

### Testing JSON Operations  
The plugin parses JSON responses from Konnected devices:
```bash
python3 -c "import json; test_json = '{\"mac\": \"12:34:56:78:9A:BC\", \"sensors\": [{\"zone\": 1, \"state\": 0}]}'; parsed = json.loads(test_json); print('JSON parsing: SUCCESS')"
```

### Testing Socket and Threading
The plugin uses socket operations for SSDP discovery and threading for background monitoring:
```bash
python3 -c "import socket, threading; print('Socket and threading modules: SUCCESS')"
```

## Common Tasks

### Running Tests
- `python3 test_plugin.py` - Run simulation test (takes <1 second)
- Output shows simulated device response and parsed sensor states

### Code Validation
- `python3 -m py_compile *.py` - Compile all Python files (takes <1 second)
- `python3 -c "import xml.etree.ElementTree as ET; [ET.parse(f) for f in ['Actions.xml', 'Devices.xml', 'MenuItems.xml', 'PluginConfig.xml', 'Info.plist']]"` - Validate XML

### Plugin Import Test
- `python3 -c "import plugin"` - Test plugin import (expect "WARNING: indigo module not available" - this is normal)

## Plugin Limitations and Context

### Important Constraints
- This is an Indigo plugin, NOT a standalone Python application
- Cannot be "built" or "run" in traditional sense - requires Indigo Home Automation software
- The `indigo` module is only available within Indigo environment
- Network access may be limited in testing environment (HTTP requests to external hosts fail)

### What Works in Testing Environment
- Python syntax validation
- Plugin logic simulation via test_plugin.py
- JSON parsing and data manipulation
- Socket and threading operations (for SSDP discovery)
- XML configuration validation
- Import testing with mock indigo module

### What Cannot Be Tested
- Actual communication with Konnected hardware
- Integration with Indigo Home Automation system
- Real device discovery via SSDP
- Live sensor monitoring and state updates

## Repository Structure

### Root Directory Contents
```
.
├── plugin.py              # Main plugin code (41KB, ~947 lines)
├── test_plugin.py          # Test script (3.6KB, ~128 lines)  
├── Actions.xml             # Plugin actions definition
├── Devices.xml             # Device type definitions
├── MenuItems.xml           # Menu structure
├── PluginConfig.xml        # Plugin preferences  
├── Info.plist              # Plugin metadata
├── README.md               # Comprehensive documentation
├── CHANGELOG.md            # Version history
├── LICENSE                 # MIT License
└── examples/README.md      # Configuration examples
```

### Configuration Files Purpose
- **Actions.xml**: Defines device discovery, status refresh, connection test, and output activation actions
- **Devices.xml**: Configures Panel (with IP/polling), Sensor (with zone/type), and Output (with zone/type) devices
- **MenuItems.xml**: Plugin menu items for device discovery and settings  
- **PluginConfig.xml**: Debug logging, timeouts, auto-discovery, and retry settings

## Development Guidelines

### Making Changes to Plugin Logic  
1. Modify `plugin.py` as needed
2. Run `python3 -m py_compile plugin.py` to check syntax
3. Run `python3 test_plugin.py` to validate logic
4. Test import: `python3 -c "import plugin"`

### Modifying Configuration
1. Edit appropriate XML file (Actions.xml, Devices.xml, etc.)
2. Validate XML syntax using Python ElementTree
3. No restart or rebuild required for XML changes

### Adding New Features
1. Update `plugin.py` with new functionality
2. Add corresponding XML configuration if needed (new device types, actions, etc.)
3. Update `test_plugin.py` with test cases for new features
4. Validate all changes using the standard validation steps