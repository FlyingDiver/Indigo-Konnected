#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Konnected Plugin for Indigo Home Automation
Supports Konnected security panel devices and sensors

Author: FlyingDiver
Version: 1.0.0
"""

import json
import socket
import threading
import time
from datetime import datetime

# Check for required modules
try:
    import requests
except ImportError:
    print("ERROR: requests module is required but not installed")
    print("Please install with: pip3 install requests")
    raise

try:
    import indigo
except ImportError:
    # This is expected when testing outside of Indigo
    print("WARNING: indigo module not available (normal when testing)")
    # Create a mock indigo module for testing
    class MockIndigo:
        class PluginBase:
            def __init__(self, *args, **kwargs):
                pass
        class Dict(dict):
            pass
        class kDeviceAction:
            TurnOn = "turnOn"
            TurnOff = "turnOff"
            Toggle = "toggle"
        server = None
        devices = None
    
    indigo = MockIndigo()

# Constants for Konnected API
KONNECTED_DISCOVERY_PORT = 1901
KONNECTED_DEFAULT_PORT = 80
DISCOVERY_MESSAGE = b"SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: ssdp:discover\r\nST: urn:konnected-io:device:Security:1\r\nMX: 5\r\n\r\n"

################################################################################
class Plugin(indigo.PluginBase):
    """Main plugin class for Konnected integration"""
    
    def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs):
        super(Plugin, self).__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs)
        
        self.debug = plugin_prefs.get("debug", False)
        self.discovery_timeout = int(plugin_prefs.get("discovery_timeout", "5"))
        self.connection_timeout = int(plugin_prefs.get("connection_timeout", "10"))
        self.auto_discovery = plugin_prefs.get("auto_discovery", True)
        self.retry_failed_connections = plugin_prefs.get("retry_failed_connections", True)
        
        self.device_list = {}
        self.panel_devices = {}
        self.update_threads = {}
        
        # Set up logging
        if self.debug:
            self.logger.setLevel(10)  # Debug level
        else:
            self.logger.setLevel(20)  # Info level
        
        self.logger.info("Konnected Plugin initialized")

    def startup(self):
        """Plugin startup"""
        self.logger.info("Konnected Plugin starting up")
        
        # Start device discovery if enabled
        if self.auto_discovery:
            self.discover_devices()
        
        # Start update threads for existing devices
        for device in indigo.devices.iter("self"):
            if device.deviceTypeId == "konnectedPanel":
                self.start_device_monitoring(device)

    def shutdown(self):
        """Plugin shutdown"""
        self.logger.info("Konnected Plugin shutting down")
        
        # Stop all monitoring threads
        for thread in self.update_threads.values():
            thread.stop()
            thread.join(timeout=5)

    def deviceStartComm(self, device):
        """Start communication with a device"""
        self.logger.info(f"Starting communication with device: {device.name}")
        
        if device.deviceTypeId == "konnectedPanel":
            self.start_device_monitoring(device)
        elif device.deviceTypeId in ["konnectedSensor", "konnectedOutput"]:
            # These devices are managed through their parent panel
            self.logger.debug(f"Sensor/output device {device.name} managed by panel")

    def deviceStopComm(self, device):
        """Stop communication with a device"""
        self.logger.info(f"Stopping communication with device: {device.name}")
        
        if device.id in self.update_threads:
            self.update_threads[device.id].stop()
            del self.update_threads[device.id]

    def start_device_monitoring(self, device):
        """Start monitoring thread for a Konnected panel device"""
        if device.id in self.update_threads:
            self.update_threads[device.id].stop()
        
        thread = KonnectedMonitorThread(self, device)
        thread.daemon = True
        thread.start()
        self.update_threads[device.id] = thread

    def discover_devices(self):
        """Discover Konnected devices on the network using SSDP"""
        self.logger.info("Starting Konnected device discovery")
        
        try:
            # Create UDP socket for SSDP discovery
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.discovery_timeout)
            
            # Send discovery message
            sock.sendto(DISCOVERY_MESSAGE, ("239.255.255.250", 1900))
            
            discovered = []
            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    response = data.decode('utf-8')
                    
                    if "konnected-io" in response.lower():
                        ip = addr[0]
                        self.logger.info(f"Discovered Konnected device at {ip}")
                        discovered.append(ip)
                        
                except socket.timeout:
                    break
                    
            sock.close()
            
            self.logger.info(f"Discovery complete. Found {len(discovered)} devices")
            return discovered
            
        except Exception as e:
            self.logger.error(f"Error during device discovery: {e}")
            return []

    def get_device_status(self, ip_address, port=80, auth_token=None):
        """Get status information from a Konnected device"""
        try:
            url = f"http://{ip_address}:{port}/status"
            headers = {}
            
            if auth_token:
                headers['Authorization'] = f'Bearer {auth_token}'
            
            response = requests.get(url, headers=headers, timeout=self.connection_timeout)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            self.logger.error(f"Error getting device status from {ip_address}: {e}")
            return None

    def update_sensor_state(self, device, zone_data):
        """Update sensor state based on zone data from Konnected device"""
        try:
            zone_number = int(device.pluginProps.get("zone_number", "1"))
            invert_logic = device.pluginProps.get("invert_logic", False)
            
            # Find the zone data for this sensor
            zone_state = None
            for zone in zone_data.get("sensors", []):
                if zone.get("zone") == zone_number:
                    zone_state = zone.get("state")
                    break
            
            if zone_state is not None:
                # Convert state (0/1) to boolean
                sensor_active = bool(zone_state)
                
                # Apply invert logic if configured
                if invert_logic:
                    sensor_active = not sensor_active
                
                # Update device states
                device.updateStateOnServer("sensorValue", sensor_active)
                device.updateStateOnServer("onOffState", sensor_active)
                
                self.logger.debug(f"Updated sensor {device.name} - Zone {zone_number}: {sensor_active}")
            
        except Exception as e:
            self.logger.error(f"Error updating sensor state for {device.name}: {e}")

    def set_output_state(self, device, state):
        """Set the state of a Konnected output device"""
        try:
            # Get panel device
            panel_device_id = device.pluginProps.get("panel_device")
            if not panel_device_id:
                self.logger.error(f"No panel device configured for output {device.name}")
                return False
                
            panel_device = indigo.devices.get(int(panel_device_id))
            if not panel_device:
                self.logger.error(f"Panel device not found for output {device.name}")
                return False
            
            ip_address = panel_device.pluginProps.get("ip_address")
            port = int(panel_device.pluginProps.get("port", "80"))
            auth_token = panel_device.pluginProps.get("auth_token")
            zone_number = int(device.pluginProps.get("zone_number", "7"))
            
            # Prepare request
            url = f"http://{ip_address}:{port}/device"
            headers = {'Content-Type': 'application/json'}
            
            if auth_token:
                headers['Authorization'] = f'Bearer {auth_token}'
            
            data = {
                "pin": zone_number,
                "state": 1 if state else 0
            }
            
            response = requests.put(url, json=data, headers=headers, timeout=self.connection_timeout)
            response.raise_for_status()
            
            # Update device state
            device.updateStateOnServer("onOffState", state)
            self.logger.info(f"Set output {device.name} to {'ON' if state else 'OFF'}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting output state for {device.name}: {e}")
            return False

    def actionControlDevice(self, action, device):
        """Handle device control actions"""
        if device.deviceTypeId == "konnectedOutput":
            if action.deviceAction == indigo.kDeviceAction.TurnOn:
                self.set_output_state(device, True)
            elif action.deviceAction == indigo.kDeviceAction.TurnOff:
                self.set_output_state(device, False)
            elif action.deviceAction == indigo.kDeviceAction.Toggle:
                current_state = device.states.get("onOffState", False)
                self.set_output_state(device, not current_state)

    def get_panel_devices(self, filter="", values_dict=None, type_id="", target_id=0):
        """Return list of panel devices for device configuration UI"""
        panel_list = []
        
        for device in indigo.devices.iter("self.konnectedPanel"):
            panel_list.append((device.id, device.name))
        
        return panel_list

    def validatePrefsConfigUi(self, values_dict):
        """Validate plugin preferences"""
        errors_dict = indigo.Dict()
        
        # Validate discovery timeout
        try:
            timeout = int(values_dict.get("discovery_timeout", "5"))
            if timeout < 1 or timeout > 60:
                errors_dict["discovery_timeout"] = "Discovery timeout must be between 1 and 60 seconds"
        except ValueError:
            errors_dict["discovery_timeout"] = "Discovery timeout must be a valid number"
        
        # Validate connection timeout
        try:
            timeout = int(values_dict.get("connection_timeout", "10"))
            if timeout < 1 or timeout > 120:
                errors_dict["connection_timeout"] = "Connection timeout must be between 1 and 120 seconds"
        except ValueError:
            errors_dict["connection_timeout"] = "Connection timeout must be a valid number"
        
        return (len(errors_dict) == 0, values_dict, errors_dict)

    def closedPrefsConfigUi(self, values_dict, user_cancelled):
        """Handle preferences dialog closing"""
        if not user_cancelled:
            # Update plugin settings
            self.debug = values_dict.get("debug", False)
            self.discovery_timeout = int(values_dict.get("discovery_timeout", "5"))
            self.connection_timeout = int(values_dict.get("connection_timeout", "10"))
            self.auto_discovery = values_dict.get("auto_discovery", True)
            self.retry_failed_connections = values_dict.get("retry_failed_connections", True)
            
            # Update logging level
            if self.debug:
                self.logger.setLevel(10)  # Debug level
            else:
                self.logger.setLevel(20)  # Info level
            
            self.logger.info("Plugin preferences updated")

    def validateDeviceConfigUi(self, values_dict, type_id, device_id):
        """Validate device configuration"""
        errors_dict = indigo.Dict()
        
        if type_id == "konnectedPanel":
            # Validate IP address
            ip_address = values_dict.get("ip_address", "").strip()
            if not ip_address:
                errors_dict["ip_address"] = "IP address is required"
            else:
                # Basic IP validation
                parts = ip_address.split(".")
                if len(parts) != 4:
                    errors_dict["ip_address"] = "Invalid IP address format"
                else:
                    for part in parts:
                        try:
                            num = int(part)
                            if num < 0 or num > 255:
                                errors_dict["ip_address"] = "Invalid IP address range"
                                break
                        except ValueError:
                            errors_dict["ip_address"] = "Invalid IP address format"
                            break
            
            # Validate port
            try:
                port = int(values_dict.get("port", "80"))
                if port < 1 or port > 65535:
                    errors_dict["port"] = "Port must be between 1 and 65535"
            except ValueError:
                errors_dict["port"] = "Port must be a valid number"
            
            # Validate poll frequency
            try:
                freq = int(values_dict.get("poll_frequency", "30"))
                if freq < 5 or freq > 600:
                    errors_dict["poll_frequency"] = "Poll frequency must be between 5 and 600 seconds"
            except ValueError:
                errors_dict["poll_frequency"] = "Poll frequency must be a valid number"
        
        elif type_id == "konnectedSensor":
            # Validate panel device selection
            panel_device = values_dict.get("panel_device")
            if not panel_device:
                errors_dict["panel_device"] = "A panel device must be selected"
            
            # Validate zone number
            try:
                zone = int(values_dict.get("zone_number", "1"))
                if zone < 1 or zone > 12:
                    errors_dict["zone_number"] = "Zone number must be between 1 and 12"
            except ValueError:
                errors_dict["zone_number"] = "Zone number must be a valid number"
        
        elif type_id == "konnectedOutput":
            # Validate panel device selection
            panel_device = values_dict.get("panel_device")
            if not panel_device:
                errors_dict["panel_device"] = "A panel device must be selected"
            
            # Validate zone number
            try:
                zone = int(values_dict.get("zone_number", "7"))
                if zone < 1 or zone > 12:
                    errors_dict["zone_number"] = "Zone number must be between 1 and 12"
            except ValueError:
                errors_dict["zone_number"] = "Zone number must be a valid number"
        
        return (len(errors_dict) == 0, values_dict, errors_dict)

    ################################################################################
    # Action Methods
    ################################################################################
    
    def discover_devices_action(self, plugin_action, device):
        """Action method to discover Konnected devices"""
        discovered = self.discover_devices()
        
        if discovered:
            message = f"Discovered {len(discovered)} Konnected device(s):\n"
            for ip in discovered:
                message += f"  - {ip}\n"
            message += "\nYou can now create panel devices with these IP addresses."
        else:
            message = "No Konnected devices found on the network."
        
        indigo.server.log(message)

    def refresh_panel_status_action(self, plugin_action, device):
        """Action method to refresh panel status immediately"""
        ip_address = device.pluginProps.get("ip_address")
        port = int(device.pluginProps.get("port", "80"))
        auth_token = device.pluginProps.get("auth_token")
        
        status = self.get_device_status(ip_address, port, auth_token)
        
        if status:
            device.updateStateOnServer("connection_status", "Connected")
            device.updateStateOnServer("zones_configured", len(status.get("sensors", [])))
            
            message = f"Panel {device.name} status refreshed successfully:\n"
            message += f"  - Connection: Connected\n"
            message += f"  - Zones configured: {len(status.get('sensors', []))}\n"
            message += f"  - MAC Address: {status.get('mac', 'Unknown')}\n"
            message += f"  - Model: {status.get('model', 'Unknown')}"
            
        else:
            device.updateStateOnServer("connection_status", "Disconnected")
            message = f"Failed to connect to panel {device.name} at {ip_address}:{port}"
        
        indigo.server.log(message)

    def test_panel_connection_action(self, plugin_action, device):
        """Action method to test panel connection"""
        self.refresh_panel_status_action(plugin_action, device)

    def activate_output_action(self, plugin_action, device):
        """Action method to activate an output for a specified duration"""
        duration = int(plugin_action.props.get("duration", "5"))
        
        if self.set_output_state(device, True):
            if duration > 0:
                # Schedule deactivation after duration
                def deactivate():
                    time.sleep(duration)
                    self.set_output_state(device, False)
                    self.logger.info(f"Automatically deactivated output {device.name} after {duration} seconds")
                
                thread = threading.Thread(target=deactivate)
                thread.daemon = True
                thread.start()
                
                self.logger.info(f"Activated output {device.name} for {duration} seconds")
            else:
                self.logger.info(f"Activated output {device.name} permanently")

    ################################################################################
    # Menu Methods
    ################################################################################
    
    def menu_discover_devices(self):
        """Menu method to discover Konnected devices"""
        discovered = self.discover_devices()
        
        if discovered:
            message = f"Discovered {len(discovered)} Konnected device(s):\n"
            for ip in discovered:
                message += f"  - {ip}\n"
            message += "\nYou can now create panel devices with these IP addresses."
        else:
            message = "No Konnected devices found on the network."
        
        indigo.server.log(message)

    def menu_plugin_settings(self):
        """Menu method to open plugin settings"""
        # This will open the plugin preferences dialog
        pass

    def menu_help(self):
        """Menu method to display help information"""
        help_text = """
Konnected Plugin Help

Device Types:
- Konnected Panel: The main controller device that connects to your network
- Konnected Sensor: Individual sensors (door/window, motion, smoke, etc.)
- Konnected Output: Relay outputs for sirens, strobes, etc.

Setup Instructions:
1. Use "Discover Konnected Devices" to find devices on your network
2. Create a Konnected Panel device with the discovered IP address
3. Create Konnected Sensor and Output devices, linking them to the panel
4. Configure zone numbers and sensor types as needed

For more information, visit:
https://github.com/FlyingDiver/Indigo-Konnected
        """
        
        indigo.server.log(help_text)

################################################################################
class KonnectedMonitorThread(threading.Thread):
    """Thread to monitor a Konnected panel device"""
    
    def __init__(self, plugin, device):
        super(KonnectedMonitorThread, self).__init__()
        self.plugin = plugin
        self.device = device
        self.stop_thread = False
        
    def stop(self):
        """Stop the monitoring thread"""
        self.stop_thread = True
        
    def run(self):
        """Main monitoring loop"""
        ip_address = self.device.pluginProps.get("ip_address")
        port = int(self.device.pluginProps.get("port", "80"))
        auth_token = self.device.pluginProps.get("auth_token")
        poll_frequency = int(self.device.pluginProps.get("poll_frequency", "30"))
        
        self.plugin.logger.debug(f"Starting monitor thread for panel {self.device.name}")
        
        while not self.stop_thread:
            try:
                # Get device status
                status = self.plugin.get_device_status(ip_address, port, auth_token)
                
                if status:
                    # Update panel connection status
                    self.device.updateStateOnServer("connection_status", "Connected")
                    self.device.updateStateOnServer("zones_configured", len(status.get("sensors", [])))
                    
                    # Reset consecutive error counter on successful connection
                    if hasattr(self, 'consecutive_errors'):
                        self.consecutive_errors = 0
                    
                    # Update associated sensor devices
                    for sensor_device in indigo.devices.iter("self.konnectedSensor"):
                        panel_id = sensor_device.pluginProps.get("panel_device")
                        if panel_id and int(panel_id) == self.device.id:
                            self.plugin.update_sensor_state(sensor_device, status)
                            
                else:
                    # Handle connection failure
                    if not hasattr(self, 'consecutive_errors'):
                        self.consecutive_errors = 0
                    
                    self.consecutive_errors += 1
                    
                    if self.plugin.retry_failed_connections and self.consecutive_errors < 5:
                        # Update connection status to retrying
                        self.device.updateStateOnServer("connection_status", "Retrying")
                        self.plugin.logger.warning(f"Connection failed for {self.device.name}, attempt {self.consecutive_errors}/5")
                    else:
                        # Update connection status to disconnected
                        self.device.updateStateOnServer("connection_status", "Disconnected")
                    
            except Exception as e:
                self.plugin.logger.error(f"Error in monitor thread for {self.device.name}: {e}")
                self.device.updateStateOnServer("connection_status", "Error")
                
                if not hasattr(self, 'consecutive_errors'):
                    self.consecutive_errors = 0
                
                self.consecutive_errors += 1
                
                # If too many consecutive errors, increase poll frequency to reduce load
                if self.consecutive_errors >= 3:
                    poll_frequency = min(poll_frequency * 2, 300)  # Cap at 5 minutes
                    self.plugin.logger.warning(f"Increased poll frequency to {poll_frequency}s due to errors")
                
            # Wait for next poll cycle
            for _ in range(poll_frequency * 10):  # Check stop flag every 0.1 seconds
                if self.stop_thread:
                    break
                time.sleep(0.1)
        
        self.plugin.logger.debug(f"Monitor thread stopped for panel {self.device.name}")