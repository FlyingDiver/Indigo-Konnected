#!/usr/bin/env python3
"""
Simple test script to validate plugin functionality without actual hardware
"""

import json
import time
from datetime import datetime

# Import our EventSource client for testing
try:
    import sys
    import os
    # Add the Server Plugin directory to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Konnected.indigoPlugin', 'Contents', 'Server Plugin'))
    from plugin import EventSourceClient
    EVENTSOURCE_AVAILABLE = True
except ImportError:
    EVENTSOURCE_AVAILABLE = False
    print("WARNING: Could not import EventSource client from plugin")

def simulate_konnected_response():
    """Simulate a Konnected device status response"""
    return {
        "mac": "12:34:56:78:9A:BC",
        "model": "Konnected Alarm Panel",
        "version": "2.3.0",
        "ip": "192.168.1.100",
        "port": 80,
        "sensors": [
            {
                "zone": 1,
                "state": 0,
                "type": "contact"
            },
            {
                "zone": 2, 
                "state": 1,
                "type": "motion"
            },
            {
                "zone": 3,
                "state": 0,
                "type": "smoke"
            }
        ]
    }

def simulate_gdo_response():
    """Simulate a GDO Blaq device status response"""
    return {
        "door": {
            "id": "garage_door",
            "state": "CLOSED",
            "current_operation": "IDLE", 
            "value": 0
        },
        "light": {
            "id": "garage_light",
            "state": "OFF"
        },
        "lock": {
            "id": "lock", 
            "state": "UNLOCKED",
            "value": 0
        },
        "motion": {
            "id": "motion",
            "state": "OFF",
            "value": False
        },
        "obstruction": {
            "id": "obstruction",
            "state": "OFF", 
            "value": False
        }
    }

def simulate_sse_events():
    """Simulate SSE events from a GDO device"""
    return [
        {
            'type': 'door',
            'data': json.dumps({
                "id": "garage_door",
                "state": "OPENING",
                "current_operation": "OPEN",
                "value": 0.25
            })
        },
        {
            'type': 'state', 
            'data': json.dumps({
                "door": {
                    "id": "garage_door",
                    "state": "OPEN",
                    "current_operation": "IDLE",
                    "value": 1.0
                },
                "light": {
                    "id": "garage_light", 
                    "state": "ON"
                }
            })
        },
        {
            'type': 'light',
            'data': json.dumps({
                "id": "garage_light",
                "state": "OFF"
            })
        }
    ]

def test_eventsource_parsing():
    """Test EventSource event parsing logic"""
    print("\n" + "=" * 40)
    print("Testing EventSource Event Parsing")
    print("=" * 40)
    
    if not EVENTSOURCE_AVAILABLE:
        print("EventSource client not available, skipping SSE tests")
        return
    
    # Create a mock EventSource client to test parsing
    client = EventSourceClient("http://test.example.com/events")
    
    # Test SSE event data parsing
    test_events = [
        "event: door\ndata: {\"state\": \"OPEN\"}\n",
        "event: light\ndata: {\"state\": \"ON\"}\nid: 123\n",
        "data: {\"type\": \"heartbeat\"}\n",
        "event: state\ndata: {\"door\": {\"state\": \"CLOSED\"}, \"light\": {\"state\": \"OFF\"}}\nretry: 5000\n"
    ]
    
    print("Testing SSE event parsing:")
    for i, event_data in enumerate(test_events):
        parsed_event = client._parse_sse_event(event_data)
        print(f"  Event {i+1}:")
        print(f"    Type: {parsed_event['type']}")
        print(f"    Data: {parsed_event['data']}")
        if parsed_event['id']:
            print(f"    ID: {parsed_event['id']}")
        if parsed_event['retry']:
            print(f"    Retry: {parsed_event['retry']}")
        print()
    
    # Test event callback mechanism
    events_received = []
    
    def test_callback(event):
        events_received.append(event)
    
    client.add_event_listener('door', test_callback)
    client.add_event_listener('light', test_callback)
    
    # Simulate firing events
    simulated_events = simulate_sse_events()
    for event in simulated_events:
        client._fire_event(event)
    
    print(f"Events received by callbacks: {len(events_received)}")
    for i, event in enumerate(events_received):
        print(f"  Callback {i+1}: Type={event['type']}, Data={event['data'][:50]}...")
    
    print("EventSource parsing tests completed!")

def test_gdo_sse_logic():
    """Test GDO-specific SSE event handling logic"""
    print("\n" + "=" * 40)
    print("Testing GDO SSE Event Logic")
    print("=" * 40)
    
    # Simulate the logic that would happen in _handle_sse_event
    simulated_events = simulate_sse_events()
    
    for i, event in enumerate(simulated_events):
        print(f"Processing SSE Event {i+1}:")
        event_type = event.get('type', 'message')
        data = event.get('data', '')
        
        try:
            event_data = json.loads(data) if data else {}
            
            if event_type == 'door':
                print(f"  Door Event: {event_data}")
                print(f"    - State: {event_data.get('state')}")
                print(f"    - Operation: {event_data.get('current_operation')}")
                print(f"    - Position: {int(event_data.get('value', 0) * 100)}%")
                
            elif event_type == 'light':
                print(f"  Light Event: {event_data}")
                print(f"    - State: {event_data.get('state')}")
                
            elif event_type == 'state':
                print(f"  State Update Event:")
                if 'door' in event_data:
                    door = event_data['door']
                    print(f"    - Door: {door.get('state')} ({int(door.get('value', 0) * 100)}%)")
                if 'light' in event_data:
                    light = event_data['light']
                    print(f"    - Light: {light.get('state')}")
                    
        except json.JSONDecodeError as e:
            print(f"  Error parsing event data: {e}")
        
        print()
    
    print("GDO SSE event logic tests completed!")

def test_plugin_logic():
    """Test core plugin logic without Indigo"""
    print("Testing Konnected Plugin Logic")
    print("=" * 40)
    
    # Test regular panel status response parsing
    status = simulate_konnected_response()
    print(f"Simulated device response:")
    print(json.dumps(status, indent=2))
    
    # Test sensor state interpretation
    print(f"\nSensor states:")
    for sensor in status.get("sensors", []):
        zone = sensor.get("zone")
        state = sensor.get("state")
        sensor_type = sensor.get("type")
        
        # Convert state to boolean (same logic as plugin)
        sensor_active = bool(state)
        
        print(f"  Zone {zone} ({sensor_type}): {'ACTIVE' if sensor_active else 'INACTIVE'}")
    
    print(f"\nDevice info:")
    print(f"  MAC: {status.get('mac')}")
    print(f"  Model: {status.get('model')}")
    print(f"  Version: {status.get('version')}")
    print(f"  Zones configured: {len(status.get('sensors', []))}")
    
    # Test GDO Blaq functionality
    print("\n" + "=" * 40)
    print("Testing GDO Blaq Logic")
    print("=" * 40)
    
    gdo_status = simulate_gdo_response()
    print(f"Simulated GDO response:")
    print(json.dumps(gdo_status, indent=2))
    
    # Test GDO state interpretation
    print(f"\nGDO states:")
    if 'door' in gdo_status:
        door = gdo_status['door']
        print(f"  Door: {door.get('state')} - {door.get('current_operation')} ({int(door.get('value', 0) * 100)}%)")
    
    if 'light' in gdo_status:
        light = gdo_status['light'] 
        print(f"  Light: {light.get('state')}")
    
    if 'lock' in gdo_status:
        lock = gdo_status['lock']
        print(f"  Lock: {lock.get('state')}")
    
    if 'motion' in gdo_status:
        motion = gdo_status['motion']
        print(f"  Motion: {'DETECTED' if motion.get('value') else 'NONE'}")
        
    if 'obstruction' in gdo_status:
        obstruction = gdo_status['obstruction']
        print(f"  Obstruction: {'PRESENT' if obstruction.get('value') else 'CLEAR'}")
    
    print("All tests completed successfully!")
    
    # Test EventSource functionality
    test_eventsource_parsing()
    test_gdo_sse_logic()

if __name__ == "__main__":
    test_plugin_logic()