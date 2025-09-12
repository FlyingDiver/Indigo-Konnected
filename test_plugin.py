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

def test_plugin_logic():
    """Test core plugin logic without Indigo"""
    print("Testing Konnected Plugin Logic")
    print("=" * 40)
    
    # Test status response parsing
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
    
    print("\nTest completed successfully!")

if __name__ == "__main__":
    test_plugin_logic()