# Support

## Getting Help

If you need help with BeatBoard, here are the best ways to get assistance:

### Documentation

- [README.md](../README.md) - Installation, usage, and troubleshooting guide
- [Contributing Guide](../.github/CONTRIBUTING.md) - For development and contribution
  questions
- [Hardware Documentation](../docs/hardware.md) - Hardware support and integration guide

### Community Support

- [GitHub Issues](https://github.com/abdellatif-temsamani/BeatBoard/issues) -
  Report bugs, request features, or ask questions
- [GitHub Discussions](https://github.com/abdellatif-temsamani/BeatBoard/discussions) -
  General discussions and Q&A

### Before Asking for Help

Please check the following first:

1. The [README.md](../README.md) for common issues and solutions
2. Existing [issues](https://github.com/abdellatif-temsamani/BeatBoard/issues)
   to see if your question has been asked before
3. The [troubleshooting section](../README.md#troubleshooting) in the README

When asking for help, please provide:

- Your operating system and version (Linux/Windows)
- Python version
- Platform-specific info:
  - Linux: `playerctl` version
  - Windows: Spotify API configuration status
- Steps to reproduce the issue
- Any error messages or logs
- Command used (include `--api` flag if applicable)

## Platform-Specific Support

### Linux Support

For Linux-specific issues:
- Ensure `playerctl` is installed and working
- Check USB permissions for hardware access
- Verify hardware detection with `--debug` flag
- Check system logs for USB/driver issues

### When using `--api` flag (any platform)

For issues when using the `--api` flag (Linux/Mac/Windows):
- Verify Spotify Developer credentials are configured
- Check firewall settings for OAuth callback (port 8888)
- Verify hardware tool availability (razer-cli, asusctl)
- Check firewall/antivirus isn't blocking BeatBoard

### Platform-Specific Notes

**Linux:** Can use either `playerctl` (default) or `--api` flag
**macOS/Windows:** Must use `--api` flag since `playerctl` is not available

Thank you for using BeatBoard! 🎵💡
