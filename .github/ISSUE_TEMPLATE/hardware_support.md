---
name: Hardware Support Request
about: Request support for a new RGB keyboard or hardware device
description: Request support for a new RGB keyboard or hardware device
title: "[HARDWARE] "
labels: ["hardware", "enhancement", "triage"]
assignees: []
---

## Device Information
**Device Name/Model:** [e.g., Razer BlackWidow V3, Corsair K57 RGB]

**Manufacturer:** [e.g., Razer, Corsair, Logitech]

**Connection Type:** [e.g., USB, Bluetooth, Wireless]

**RGB Capabilities:** [e.g., per-key RGB, zone-based, single color]

## Technical Details
**USB Vendor ID:** [if known, e.g., 0x1532]

**USB Product ID:** [if known, e.g., 0x0243]

**Driver/Protocol:** [if known, e.g., HID, proprietary]

**Linux Compatibility:** [e.g., works with OpenRGB, requires custom driver]

## Current Status
- [ ] Device is detected by Linux
- [ ] Basic RGB control works (via other software)
- [ ] Device uses standard protocols
- [ ] Custom implementation needed

## Additional Context
Provide any additional information that might help with implementation:
- Links to device specifications
- Existing open-source drivers or projects
- Screenshots of device control software
- Community forums or documentation

## Implementation Notes
If you have technical knowledge:
- Preferred approach (extend existing drivers, new module)
- Similar devices already supported
- Potential challenges or requirements

## Checklist
- [ ] This device is RGB-capable
- [ ] Device works on Linux
- [ ] No existing support in BeatBoard
- [ ] Willing to help test implementations