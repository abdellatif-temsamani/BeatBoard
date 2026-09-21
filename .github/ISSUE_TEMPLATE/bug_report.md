---
name: Bug Report
about: Report bugs and unexpected behavior in BeatBoard
description: Report a bug or unexpected behavior
title: "[BUG] "
labels: ["bug", "triage"]
assignees: []
---

## Description
A clear and concise description of the bug.

## Steps to Reproduce
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

## Expected Behavior
A clear and concise description of what you expected to happen.

## Actual Behavior
What actually happened instead.

## Environment
- OS: [e.g., Ubuntu 22.04, Fedora 38, macOS 14, Windows 10/11]
- Python Version: [e.g., 3.11, 3.12]
- BeatBoard Version: [e.g., 0.3.0]
- Hardware: [e.g., Logitech G213 Prodigy, Razer BlackWidow]
- Spotify Desktop Version: [e.g., 1.2.8.923]
- Command used: [e.g., `beatboard` (Linux with playerctl) or `beatboard --api` (any platform)]

## Logs/Output
If applicable, add logs or command output to help explain your problem.

```bash
# Command used (use --api flag if playerctl is unavailable on your platform)
beatboard --debug
# or if using Spotify API:
beatboard --api --debug

# Output/Error
```

## Additional Context
Add any other context about the problem here, such as:
- When did this start happening?
- Does this happen with all songs or specific ones?
- Any recent changes to your system?

## Checklist
- [ ] I have checked the [troubleshooting section](https://github.com/abdellatif-temsamani/BeatBoard#troubleshooting) in the README
- [ ] I have searched for similar issues in the repository
- [ ] I am using the latest version of BeatBoard