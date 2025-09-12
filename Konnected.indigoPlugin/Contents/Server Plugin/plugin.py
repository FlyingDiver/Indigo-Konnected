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
import re

# Check for required modules
try:
    import requests
except ImportError:
    print("ERROR: requests module is required but not installed")
    print("Please install with: pip3 install requests")
    raise

try:
    import zeroconf
    from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
    ZEROCONF_AVAILABLE = True
except ImportError:
    print("INFO: zeroconf module not available - mDNS discovery will be disabled")
    ZEROCONF_AVAILABLE = False
    # Create stub classes when zeroconf is not available
    class ServiceListener:
        pass
    class Zeroconf:
        pass
    class ServiceBrowser:
        pass

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

# GDO Blaq specific constants
GDO_DISCOVERY_MESSAGE = b"SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: ssdp:discover\r\nST: urn:konnected-io:device:GDO:1\r\nMX: 5\r\n\r\n"

# mDNS service types for Konnected devices
KONNECTED_MDNS_SERVICE = "_konnected._tcp.local."
GDO_MDNS_SERVICE = "_gdoblaq._tcp.local."

################################################################################
class KonnectedServiceListener(ServiceListener):
    """mDNS Service Listener for Konnected devices"""
    
    def __init__(self, plugin):
        self.plugin = plugin
        self.discovered_devices = []
        
    def add_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        """Handle service discovery"""
        info = zc.get_service_info(service_type, name)
        if info:
            # Extract IP address from service info
            addresses = info.addresses
            if addresses:
                ip_address = socket.inet_ntoa(addresses[0])
                port = info.port
                
                device_info = {
                    'ip': ip_address,
                    'port': port,
                    'name': name,
                    'service_type': service_type,
                    'properties': info.properties
                }
                
                self.discovered_devices.append(device_info)
                self.plugin.logger.info(f"mDNS discovered {service_type} device: {name} at {ip_address}:{port}")
                
    def remove_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        """Handle service removal"""
        self.plugin.logger.debug(f"mDNS service removed: {name}")
        
    def update_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        """Handle service updates"""
        self.plugin.logger.debug(f"mDNS service updated: {name}")

################################################################################
class EventSourceClient:
    """EventSource client for Server-Sent Events (SSE) connections"""
    
    def __init__(self, url, auth=None, timeout=30):
        self.url = url
        self.auth = auth
        self.timeout = timeout
        self.session = requests.Session()
        self.response = None
        self.event_callbacks = {}
        self.stop_listening = False
        
    def add_event_listener(self, event_type, callback):
        """Add a callback for specific event types"""
        if event_type not in self.event_callbacks:
            self.event_callbacks[event_type] = []
        self.event_callbacks[event_type].append(callback)
    
    def remove_event_listener(self, event_type, callback):
        """Remove a callback for specific event types"""
        if event_type in self.event_callbacks and callback in self.event_callbacks[event_type]:
            self.event_callbacks[event_type].remove(callback)
    
    def _parse_sse_event(self, event_data):
        """Parse SSE event data into event object"""
        event = {
            'type': 'message',
            'data': '',
            'id': None,
            'retry': None
        }
        
        lines = event_data.strip().split('\n')
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                if key == 'event':
                    event['type'] = value
                elif key == 'data':
                    if event['data']:
                        event['data'] += '\n'
                    event['data'] += value
                elif key == 'id':
                    event['id'] = value
                elif key == 'retry':
                    try:
                        event['retry'] = int(value)
                    except ValueError:
                        pass
        
        return event
    
    def _fire_event(self, event):
        """Fire event callbacks for the given event"""
        event_type = event.get('type', 'message')
        
        # Fire callbacks for this specific event type
        if event_type in self.event_callbacks:
            for callback in self.event_callbacks[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    print(f"Error in event callback: {e}")
        
        # Fire callbacks for 'all' events if registered
        if 'all' in self.event_callbacks:
            for callback in self.event_callbacks['all']:
                try:
                    callback(event)
                except Exception as e:
                    print(f"Error in event callback: {e}")
    
    def connect(self):
        """Establish EventSource connection"""
        try:
            headers = {
                'Accept': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }
            
            self.response = self.session.get(
                self.url,
                headers=headers,
                auth=self.auth,
                stream=True,
                timeout=self.timeout
            )
            self.response.raise_for_status()
            return True
            
        except Exception as e:
            print(f"Failed to connect to EventSource: {e}")
            return False
    
    def listen(self):
        """Listen for SSE events"""
        if not self.response:
            if not self.connect():
                return False
                
        buffer = ""
        
        try:
            for chunk in self.response.iter_content(chunk_size=1024, decode_unicode=True):
                if self.stop_listening:
                    break
                    
                if chunk:
                    buffer += chunk
                    
                    # Process complete events (separated by double newline)
                    while '\n\n' in buffer:
                        event_data, buffer = buffer.split('\n\n', 1)
                        if event_data.strip():
                            event = self._parse_sse_event(event_data)
                            self._fire_event(event)
                            
        except Exception as e:
            print(f"Error listening to EventSource: {e}")
            return False
        
        return True
    
    def close(self):
        """Close the EventSource connection"""
        self.stop_listening = True
        if self.response:
            self.response.close()
            self.response = None

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
        if hasattr(self, 'logger'):
            if self.debug:
                self.logger.setLevel(10)  # Debug level
            else:
                self.logger.setLevel(20)  # Info level
        
        if hasattr(self, 'logger'):
            self.logger.info("Konnected Plugin initialized")
        else:
            print("Konnected Plugin initialized (test mode)")

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
        elif device.deviceTypeId == "konnectedGDO":
            self.start_gdo_monitoring(device)
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

    def start_gdo_monitoring(self, device):
        """Start monitoring thread for a GDO Blaq device"""
        if device.id in self.update_threads:
            self.update_threads[device.id].stop()
        
        thread = GDOMonitorThread(self, device)
        thread.daemon = True
        thread.start()
        self.update_threads[device.id] = thread

    def discover_devices(self):
        """Discover Konnected devices on the network using SSDP and mDNS"""
        self.logger.info("Starting Konnected device discovery")
        
        discovered_devices = set()  # Use set to avoid duplicates
        
        # Try SSDP discovery first
        try:
            # Create UDP socket for SSDP discovery
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.discovery_timeout)
            
            # Send discovery message for Security panels
            sock.sendto(DISCOVERY_MESSAGE, ("239.255.255.250", 1900))
            
            ssdp_devices = []
            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    response = data.decode('utf-8')
                    
                    if "konnected-io" in response.lower():
                        ip = addr[0]
                        self.logger.info(f"SSDP discovered Konnected device at {ip}")
                        ssdp_devices.append(ip)
                        
                except socket.timeout:
                    break
                    
            sock.close()
            
            # Also try GDO discovery
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.discovery_timeout)
            sock.sendto(GDO_DISCOVERY_MESSAGE, ("239.255.255.250", 1900))
            
            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    response = data.decode('utf-8')
                    
                    if "konnected-io" in response.lower():
                        ip = addr[0]
                        self.logger.info(f"SSDP discovered GDO device at {ip}")
                        ssdp_devices.append(ip)
                        
                except socket.timeout:
                    break
                    
            sock.close()
            
            # Add SSDP discovered devices
            for ip in ssdp_devices:
                discovered_devices.add(ip)
            
            self.logger.info(f"SSDP discovery complete. Found {len(ssdp_devices)} devices")
            
        except Exception as e:
            self.logger.error(f"Error during SSDP device discovery: {e}")
        
        # Try mDNS discovery
        try:
            mdns_devices = self.discover_devices_mdns()
            for ip in mdns_devices:
                discovered_devices.add(ip)
                
        except Exception as e:
            self.logger.error(f"Error during mDNS device discovery: {e}")
        
        discovered_list = list(discovered_devices)
        self.logger.info(f"Total discovery complete. Found {len(discovered_list)} unique devices")
        return discovered_list

    def discover_devices_mdns(self):
        """Discover Konnected devices on the network using mDNS"""
        if not ZEROCONF_AVAILABLE:
            self.logger.warning("mDNS discovery not available - zeroconf module not installed")
            return []
            
        self.logger.info("Starting Konnected device discovery via mDNS")
        
        try:
            zc = Zeroconf()
            listener = KonnectedServiceListener(self)
            
            # Create browsers for both Konnected services
            browser_konnected = ServiceBrowser(zc, KONNECTED_MDNS_SERVICE, listener)
            browser_gdo = ServiceBrowser(zc, GDO_MDNS_SERVICE, listener)
            
            # Wait for discovery timeout
            time.sleep(self.discovery_timeout)
            
            # Stop browsing and close zeroconf
            browser_konnected.cancel()
            browser_gdo.cancel()
            zc.close()
            
            # Extract IP addresses from discovered devices
            discovered_ips = []
            for device in listener.discovered_devices:
                discovered_ips.append(device['ip'])
                self.logger.info(f"mDNS found device: {device['name']} ({device['service_type']}) at {device['ip']}:{device['port']}")
            
            self.logger.info(f"mDNS discovery complete. Found {len(discovered_ips)} devices")
            return discovered_ips
            
        except Exception as e:
            self.logger.error(f"Error during mDNS device discovery: {e}")
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

    def get_gdo_status(self, ip_address, port=80, username=None, password=None):
        """Get status information from a GDO Blaq device"""
        try:
            auth = None
            if username and password:
                auth = (username, password)
            
            # Get door status
            door_url = f"http://{ip_address}:{port}/cover/garage_door"
            door_response = requests.get(door_url, auth=auth, timeout=self.connection_timeout)
            door_response.raise_for_status()
            door_data = door_response.json()
            
            # Get light status
            light_url = f"http://{ip_address}:{port}/light/garage_light"
            light_response = requests.get(light_url, auth=auth, timeout=self.connection_timeout)
            light_response.raise_for_status()
            light_data = light_response.json()
            
            # Get lock status
            lock_url = f"http://{ip_address}:{port}/lock/lock"
            lock_response = requests.get(lock_url, auth=auth, timeout=self.connection_timeout)
            lock_response.raise_for_status()
            lock_data = lock_response.json()
            
            # Try to get optional sensors (motion, obstruction)
            motion_data = None
            try:
                motion_url = f"http://{ip_address}:{port}/binary_sensor/motion"
                motion_response = requests.get(motion_url, auth=auth, timeout=self.connection_timeout)
                motion_response.raise_for_status()
                motion_data = motion_response.json()
            except:
                pass  # Motion sensor not available
                
            obstruction_data = None
            try:
                obstruction_url = f"http://{ip_address}:{port}/binary_sensor/obstruction"
                obstruction_response = requests.get(obstruction_url, auth=auth, timeout=self.connection_timeout)
                obstruction_response.raise_for_status()
                obstruction_data = obstruction_response.json()
            except:
                pass  # Obstruction sensor not available
            
            return {
                'door': door_data,
                'light': light_data,
                'lock': lock_data,
                'motion': motion_data,
                'obstruction': obstruction_data
            }
            
        except Exception as e:
            self.logger.error(f"Error getting GDO status from {ip_address}: {e}")
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

    def control_gdo_door(self, device, command, position=None):
        """Control GDO Blaq garage door"""
        try:
            ip_address = device.pluginProps.get("ip_address")
            port = int(device.pluginProps.get("port", "80"))
            username = device.pluginProps.get("auth_username")
            password = device.pluginProps.get("auth_password")
            
            auth = None
            if username and password:
                auth = (username, password)
            
            # Map commands to endpoints
            endpoint_map = {
                'open': '/cover/garage_door/open',
                'close': '/cover/garage_door/close',
                'stop': '/cover/garage_door/stop',
                'toggle': '/cover/garage_door/toggle'
            }
            
            if command == 'position' and position is not None:
                url = f"http://{ip_address}:{port}/cover/garage_door/set"
                params = {'position': position / 100.0}  # Convert percentage to decimal
                response = requests.post(url, params=params, auth=auth, timeout=self.connection_timeout)
            else:
                endpoint = endpoint_map.get(command)
                if not endpoint:
                    self.logger.error(f"Unknown GDO command: {command}")
                    return False
                    
                url = f"http://{ip_address}:{port}{endpoint}"
                response = requests.post(url, auth=auth, timeout=self.connection_timeout)
            
            response.raise_for_status()
            self.logger.info(f"GDO door command '{command}' sent to {device.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error controlling GDO door for {device.name}: {e}")
            return False

    def control_gdo_light(self, device, command):
        """Control GDO Blaq garage light"""
        try:
            ip_address = device.pluginProps.get("ip_address")
            port = int(device.pluginProps.get("port", "80"))
            username = device.pluginProps.get("auth_username")
            password = device.pluginProps.get("auth_password")
            
            auth = None
            if username and password:
                auth = (username, password)
            
            # Map commands to endpoints
            endpoint_map = {
                'turn_on': '/light/garage_light/turn_on',
                'turn_off': '/light/garage_light/turn_off',
                'toggle': '/light/garage_light/toggle'
            }
            
            endpoint = endpoint_map.get(command)
            if not endpoint:
                self.logger.error(f"Unknown light command: {command}")
                return False
                
            url = f"http://{ip_address}:{port}{endpoint}"
            response = requests.post(url, auth=auth, timeout=self.connection_timeout)
            response.raise_for_status()
            
            self.logger.info(f"GDO light command '{command}' sent to {device.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error controlling GDO light for {device.name}: {e}")
            return False

    def update_gdo_states(self, device, status_data):
        """Update GDO device states based on status data"""
        if not status_data:
            return
            
        try:
            # Update door states
            if 'door' in status_data and status_data['door']:
                door_data = status_data['door']
                
                # Door state (OPEN/CLOSED)
                door_state = door_data.get('state', 'UNKNOWN')
                device.updateStateOnServer("door_state", door_state)
                
                # Current operation (IDLE/OPENING/CLOSING)
                door_operation = door_data.get('current_operation', 'UNKNOWN')
                device.updateStateOnServer("door_operation", door_operation)
                
                # Door position (0-100%)
                door_value = door_data.get('value', 0)
                door_position = int(door_value * 100) if door_value is not None else 0
                device.updateStateOnServer("door_position", door_position)
            
            # Update light state
            if 'light' in status_data and status_data['light']:
                light_data = status_data['light']
                light_state = light_data.get('state', 'OFF') == 'ON'
                device.updateStateOnServer("light_state", light_state)
            
            # Update lock state
            if 'lock' in status_data and status_data['lock']:
                lock_data = status_data['lock']
                lock_state = lock_data.get('state', 'UNKNOWN')
                device.updateStateOnServer("lock_state", lock_state)
            
            # Update motion sensor
            if 'motion' in status_data and status_data['motion']:
                motion_data = status_data['motion']
                motion_detected = motion_data.get('value', False)
                device.updateStateOnServer("motion_detected", motion_detected)
            
            # Update obstruction sensor
            if 'obstruction' in status_data and status_data['obstruction']:
                obstruction_data = status_data['obstruction']
                obstruction_detected = obstruction_data.get('value', False)
                device.updateStateOnServer("obstruction_detected", obstruction_detected)
            
            self.logger.debug(f"Updated GDO states for {device.name}")
            
        except Exception as e:
            self.logger.error(f"Error updating GDO states for {device.name}: {e}")

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
        
        elif type_id == "konnectedGDO":
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
                freq = int(values_dict.get("poll_frequency", "10"))
                if freq < 5 or freq > 600:
                    errors_dict["poll_frequency"] = "Poll frequency must be between 5 and 600 seconds"
            except ValueError:
                errors_dict["poll_frequency"] = "Poll frequency must be a valid number"
        
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
    # GDO Action Methods
    ################################################################################
    
    def open_garage_door_action(self, plugin_action, device):
        """Action method to open garage door"""
        self.control_gdo_door(device, 'open')

    def close_garage_door_action(self, plugin_action, device):
        """Action method to close garage door"""
        self.control_gdo_door(device, 'close')

    def stop_garage_door_action(self, plugin_action, device):
        """Action method to stop garage door"""
        self.control_gdo_door(device, 'stop')

    def toggle_garage_door_action(self, plugin_action, device):
        """Action method to toggle garage door"""
        self.control_gdo_door(device, 'toggle')

    def set_garage_door_position_action(self, plugin_action, device):
        """Action method to set garage door position"""
        try:
            position = int(plugin_action.props.get("position", "50"))
            position = max(0, min(100, position))  # Clamp to 0-100%
            self.control_gdo_door(device, 'position', position)
        except ValueError:
            self.logger.error("Invalid position value for garage door")

    def toggle_garage_light_action(self, plugin_action, device):
        """Action method to toggle garage light"""
        self.control_gdo_light(device, 'toggle')

    def refresh_gdo_status_action(self, plugin_action, device):
        """Action method to refresh GDO status immediately"""
        ip_address = device.pluginProps.get("ip_address")
        port = int(device.pluginProps.get("port", "80"))
        username = device.pluginProps.get("auth_username")
        password = device.pluginProps.get("auth_password")
        
        status = self.get_gdo_status(ip_address, port, username, password)
        
        if status:
            device.updateStateOnServer("connection_status", "Connected")
            self.update_gdo_states(device, status)
            
            door_state = status.get('door', {}).get('state', 'Unknown')
            message = f"GDO {device.name} status refreshed successfully:\n"
            message += f"  - Connection: Connected\n"
            message += f"  - Door State: {door_state}\n"
            message += f"  - Light: {'ON' if status.get('light', {}).get('state') == 'ON' else 'OFF'}"
            
        else:
            device.updateStateOnServer("connection_status", "Disconnected")
            message = f"Failed to connect to GDO {device.name} at {ip_address}:{port}"
        
        indigo.server.log(message)

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
class GDOMonitorThread(threading.Thread):
    """Thread to monitor a GDO Blaq device"""
    
    def __init__(self, plugin, device):
        super(GDOMonitorThread, self).__init__()
        self.plugin = plugin
        self.device = device
        self.stop_thread = False
        self.eventsource_client = None
        self.consecutive_errors = 0
        
    def stop(self):
        """Stop the monitoring thread"""
        self.stop_thread = True
        if self.eventsource_client:
            self.eventsource_client.close()
    
    def _handle_sse_event(self, event):
        """Handle incoming SSE events from GDO device"""
        try:
            event_type = event.get('type', 'message')
            data = event.get('data', '')
            
            if not data:
                return
                
            # Parse JSON data
            try:
                event_data = json.loads(data)
            except json.JSONDecodeError:
                self.plugin.logger.debug(f"Non-JSON SSE event data: {data}")
                return
            
            # Update device connection status on any successful event
            self.device.updateStateOnServer("connection_status", "Connected (SSE)")
            self.consecutive_errors = 0
            
            # Handle different event types
            if event_type == 'state' or event_type == 'message':
                # This is a general state update - parse and update states
                self.plugin.update_gdo_states(self.device, event_data)
                self.plugin.logger.debug(f"Updated GDO states via SSE for {self.device.name}")
                
            elif event_type == 'door':
                # Door-specific event
                door_data = {'door': event_data}
                self.plugin.update_gdo_states(self.device, door_data)
                self.plugin.logger.debug(f"Updated GDO door state via SSE for {self.device.name}")
                
            elif event_type == 'light':
                # Light-specific event  
                light_data = {'light': event_data}
                self.plugin.update_gdo_states(self.device, light_data)
                self.plugin.logger.debug(f"Updated GDO light state via SSE for {self.device.name}")
                
            else:
                self.plugin.logger.debug(f"Unknown SSE event type '{event_type}' for {self.device.name}")
                
        except Exception as e:
            self.plugin.logger.error(f"Error handling SSE event for {self.device.name}: {e}")
    
    def _try_eventsource_monitoring(self, ip_address, port, auth):
        """Try to use EventSource for monitoring"""
        try:
            # Try common SSE endpoints for GDO devices
            sse_endpoints = ['/events', '/stream', '/api/events', '/api/stream']
            
            for endpoint in sse_endpoints:
                sse_url = f"http://{ip_address}:{port}{endpoint}"
                
                self.plugin.logger.debug(f"Trying SSE endpoint: {sse_url}")
                
                # Create EventSource client
                self.eventsource_client = EventSourceClient(sse_url, auth=auth, timeout=30)
                
                # Add event listeners
                self.eventsource_client.add_event_listener('all', self._handle_sse_event)
                
                # Try to connect
                if self.eventsource_client.connect():
                    self.plugin.logger.info(f"Connected to SSE endpoint {sse_url} for {self.device.name}")
                    
                    # Listen for events (this blocks until connection fails or stop_thread is set)
                    success = self.eventsource_client.listen()
                    
                    if success and not self.stop_thread:
                        # Connection was closed by server or network issue
                        self.plugin.logger.warning(f"SSE connection closed for {self.device.name}")
                        
                    return success
                else:
                    # This endpoint didn't work, try the next one
                    self.eventsource_client.close()
                    self.eventsource_client = None
                    continue
            
            # No SSE endpoints worked
            self.plugin.logger.debug(f"No working SSE endpoints found for {self.device.name}")
            return False
            
        except Exception as e:
            self.plugin.logger.debug(f"EventSource monitoring failed for {self.device.name}: {e}")
            if self.eventsource_client:
                self.eventsource_client.close()
                self.eventsource_client = None
            return False
        
    def run(self):
        """Main monitoring loop for GDO devices"""
        ip_address = self.device.pluginProps.get("ip_address")
        port = int(self.device.pluginProps.get("port", "80"))
        username = self.device.pluginProps.get("auth_username")
        password = self.device.pluginProps.get("auth_password")
        use_eventsource = self.device.pluginProps.get("use_eventsource", True)
        poll_frequency = int(self.device.pluginProps.get("poll_frequency", "10"))
        
        auth = None
        if username and password:
            auth = (username, password)
        
        self.plugin.logger.debug(f"Starting GDO monitor thread for {self.device.name}")
        
        # Try EventSource first if enabled
        if use_eventsource:
            self.plugin.logger.info(f"Attempting EventSource monitoring for {self.device.name}")
            
            while not self.stop_thread:
                # Try EventSource monitoring
                sse_success = self._try_eventsource_monitoring(ip_address, port, auth)
                
                if self.stop_thread:
                    break
                    
                if not sse_success:
                    self.consecutive_errors += 1
                    
                    if self.consecutive_errors >= 3:
                        # Too many SSE failures, fall back to polling
                        self.plugin.logger.warning(f"EventSource failed {self.consecutive_errors} times for {self.device.name}, falling back to polling")
                        break
                    else:
                        # Wait and retry SSE
                        self.plugin.logger.info(f"EventSource failed for {self.device.name}, retrying in 10 seconds...")
                        for _ in range(100):  # 10 seconds with 0.1s check intervals
                            if self.stop_thread:
                                break
                            time.sleep(0.1)
                        continue
        
        # Fall back to polling mode (original implementation)
        if not self.stop_thread:
            self.plugin.logger.info(f"Using polling monitoring for {self.device.name}")
            
            while not self.stop_thread:
                try:
                    # Get device status via polling
                    status = self.plugin.get_gdo_status(ip_address, port, username, password)
                    
                    if status:
                        # Update device connection status
                        self.device.updateStateOnServer("connection_status", "Connected (Polling)")
                        
                        # Reset consecutive error counter on successful connection
                        self.consecutive_errors = 0
                        
                        # Update device states
                        self.plugin.update_gdo_states(self.device, status)
                                
                    else:
                        # Handle connection failure
                        self.consecutive_errors += 1
                        
                        if self.plugin.retry_failed_connections and self.consecutive_errors < 5:
                            # Update connection status to retrying
                            self.device.updateStateOnServer("connection_status", "Retrying")
                            self.plugin.logger.warning(f"GDO connection failed for {self.device.name}, attempt {self.consecutive_errors}/5")
                        else:
                            # Update connection status to disconnected
                            self.device.updateStateOnServer("connection_status", "Disconnected")
                        
                except Exception as e:
                    self.plugin.logger.error(f"Error in GDO monitor thread for {self.device.name}: {e}")
                    self.device.updateStateOnServer("connection_status", "Error")
                    
                    self.consecutive_errors += 1
                    
                    # If too many consecutive errors, increase poll frequency to reduce load
                    if self.consecutive_errors >= 3:
                        poll_frequency = min(poll_frequency * 2, 300)  # Cap at 5 minutes
                        self.plugin.logger.warning(f"Increased GDO poll frequency to {poll_frequency}s due to errors")
                    
                # Wait for next poll cycle
                for _ in range(poll_frequency * 10):  # Check stop flag every 0.1 seconds
                    if self.stop_thread:
                        break
                    time.sleep(0.1)
        
        self.plugin.logger.debug(f"GDO monitor thread stopped for {self.device.name}")

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