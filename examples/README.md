# Konnected Plugin Configuration Examples

This directory contains example configurations and documentation for setting up the Konnected plugin.

## Example Device Configurations

### Basic Panel Setup

1. **Konnected Panel Device**
   - Name: "Main Security Panel"
   - IP Address: "192.168.1.100"
   - Port: "80"
   - Auth Token: (leave blank if not using authentication)
   - Polling Frequency: "30" (30 seconds)

### Common Sensor Configurations

2. **Front Door Sensor**
   - Device Type: Konnected Sensor
   - Panel Device: "Main Security Panel"
   - Zone Number: "1"
   - Sensor Type: "contact" (Contact Sensor)
   - Invert Logic: false

3. **Motion Detector**
   - Device Type: Konnected Sensor
   - Panel Device: "Main Security Panel"
   - Zone Number: "2"
   - Sensor Type: "motion" (Motion Sensor)
   - Invert Logic: false

4. **Smoke Detector**
   - Device Type: Konnected Sensor
   - Panel Device: "Main Security Panel"
   - Zone Number: "3"
   - Sensor Type: "smoke" (Smoke Detector)
   - Invert Logic: false

### Output Device Configurations

5. **Siren/Alarm Output**
   - Device Type: Konnected Output
   - Panel Device: "Main Security Panel"
   - Zone Number: "7"
   - Output Type: "siren" (Siren/Alarm)

6. **Strobe Light Output**
   - Device Type: Konnected Output
   - Panel Device: "Main Security Panel"
   - Zone Number: "8"
   - Output Type: "strobe" (Strobe Light)

## Zone Number Guidelines

### Konnected Alarm Panel (6-zone)
- Zones 1-6: Sensor inputs
- Zone 7: Relay output (typically for siren)

### Konnected Alarm Panel Pro (12-zone)
- Zones 1-12: Sensor inputs
- Zones 7-12: Can be configured as relay outputs

### Zone Assignment Tips
- Use lower numbered zones (1-6) for critical sensors like entry doors
- Use higher numbered zones for less critical sensors
- Reserve zones 7+ for outputs when possible
- Check your Konnected device's web interface for current zone assignments

## Common Sensor Types and Settings

### Door/Window Sensors (Contact Sensors)
- **Sensor Type**: "contact"
- **Typical Wiring**: Normally closed (NC)
- **Invert Logic**: Usually false
- **Use Case**: Entry detection, window monitoring

### Motion Detectors
- **Sensor Type**: "motion"
- **Typical Wiring**: Normally open (NO) 
- **Invert Logic**: May need to be true depending on detector
- **Use Case**: Room occupancy, intrusion detection

### Smoke/Fire Detectors
- **Sensor Type**: "smoke"
- **Typical Wiring**: Varies by detector type
- **Invert Logic**: Check detector specifications
- **Use Case**: Fire safety monitoring

### Water Leak Sensors
- **Sensor Type**: "leak"
- **Typical Wiring**: Normally open (NO)
- **Invert Logic**: Usually false
- **Use Case**: Flood detection, appliance monitoring

## Trigger Examples

### Entry Door Alert
```
Trigger: Device State Changed
Device: Front Door Sensor
State: sensorValue
Condition: becomes true
Action: Send Email "Front door opened"
```

### Motion Detection
```
Trigger: Device State Changed
Device: Living Room Motion
State: sensorValue
Condition: becomes true
Action: Turn on lights, log event
```

### Alarm Activation
```
Trigger: Variable Changed (Security Mode)
Variable: home_security_mode
Condition: becomes "armed"
Action: Activate Siren Output for 30 seconds
```

## Troubleshooting Common Issues

### Sensor Always Shows Same State
- Check physical wiring connections
- Verify zone number matches Konnected web interface
- Try toggling "Invert Logic" setting
- Check if sensor requires external power

### Panel Connection Issues
- Verify IP address is correct and reachable
- Check that Konnected device is on same network
- Ensure device is powered on
- Try manual IP instead of DHCP reservation

### Outputs Not Responding  
- Verify zone is configured as output in Konnected interface
- Check physical relay connections
- Ensure adequate power supply for connected devices
- Test output directly from Konnected web interface first