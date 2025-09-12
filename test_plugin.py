#!/usr/bin/env python3
"""
Simple test script to validate plugin functionality without actual hardware
"""

import json
import time
from datetime import datetime

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
    
    print("\nAll tests completed successfully!")

if __name__ == "__main__":
    test_plugin_logic()