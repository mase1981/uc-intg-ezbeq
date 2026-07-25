# ezBEQ Integration for Unfolded Circle Remote 2/3

Load **BEQ** (Bass EQ) filters onto your DSP straight from your Unfolded Circle Remote 2 or Remote 3, through your [**ezBEQ**](https://github.com/3ll3d00d/ezbeq) server. Browse or search the BEQ catalogue, pick a movie, and its filters are pushed to the slot you choose - on **any** DSP ezBEQ supports (miniDSP, Monoprice HTP-1, JRiver, CamillaDSP, Q-SYS).

![ezBEQ](https://img.shields.io/badge/ezBEQ-BEQ-blue)
[![GitHub Release](https://img.shields.io/github/v/release/mase1981/uc-intg-ezbeq?style=flat-square)](https://github.com/mase1981/uc-intg-ezbeq/releases)
![License](https://img.shields.io/badge/license-MPL--2.0-blue?style=flat-square)
[![GitHub issues](https://img.shields.io/github/issues/mase1981/uc-intg-ezbeq?style=flat-square)](https://github.com/mase1981/uc-intg-ezbeq/issues)
[![Community Forum](https://img.shields.io/badge/community-forum-blue?style=flat-square)](https://unfolded.community/)
[![Discord](https://badgen.net/discord/online-members/zGVYf58)](https://discord.gg/zGVYf58)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/mase1981/uc-intg-ezbeq/total?style=flat-square)
[![Buy Me A Coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=flat-square)](https://buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-donate-blue.svg?style=flat-square)](https://paypal.me/mmiyara)
[![Github Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-30363D?&logo=GitHub-Sponsors&logoColor=EA4AAA&style=flat-square)](https://github.com/sponsors/mase1981)

## Features

BEQ restores the low-frequency content mixed into a movie's original theatrical track. ezBEQ is the server that manages loading those filters onto your DSP; this integration turns it into a native Remote experience:

- **🎬 Browse & Search the BEQ catalogue** - a media browser (by **Title A-Z**, Audio Type, Author or Year, plus full-text **search by name**) powered by your ezBEQ server. Pick a movie to load its BEQ.
- **🖼️ Movie posters** shown as thumbnails while you browse, and the loaded BEQ's **frequency-response graph** displayed on the media player.
- **🎚️ Slot control** - a Select entity per DSP device chooses which slot the load applies to.
- **📊 Live slot status** - a Sensor per slot shows exactly which BEQ is loaded (or Empty), updated in real time.
- **🔌 Works with every ezBEQ backend** - miniDSP, Monoprice HTP-1, JRiver, CamillaDSP, Q-SYS. One integration, all your DSPs.
- **⚡ Real-time updates** via ezBEQ's WebSocket, with automatic polling fallback for robustness.
- **Multi-device & multi-server** - each DSP device becomes its own media_player; add more than one ezBEQ server if you have them.

---
## ❤️ Support Development ❤️

If you find this integration useful, consider supporting development:

[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-GitHub-pink?style=for-the-badge&logo=github)](https://github.com/sponsors/mase1981)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/mmiyara)

Your support helps maintain this integration. Thank you! ❤️
---

## Requirements

- A running [**ezBEQ**](https://github.com/3ll3d00d/ezbeq) server on your network, with at least one DSP device configured in it.
- The ezBEQ server's IP address and port (default `8080`).
- Unfolded Circle Remote 2 / 3 with firmware supporting custom integrations.

## Installation

### Option 1: Remote Web Interface (Recommended)

1. Download the latest `uc-intg-ezbeq-<version>.tar.gz` from the [**Releases**](https://github.com/mase1981/uc-intg-ezbeq/releases) page.
2. Open your Remote's web interface (`http://your-remote-ip`).
3. Go to **Settings -> Integrations -> Add Integration -> Install Custom** and upload the `.tar.gz`.

### Option 2: Docker (Advanced Users)

The integration is available as a pre-built Docker image from GitHub Container Registry:

**Image**: `ghcr.io/mase1981/uc-intg-ezbeq:latest`

**Docker Compose:**
```yaml
services:
  uc-intg-ezbeq:
    image: ghcr.io/mase1981/uc-intg-ezbeq:latest
    container_name: uc-intg-ezbeq
    network_mode: host
    volumes:
      - ./config:/config
    environment:
      - UC_CONFIG_HOME=/config
      - UC_INTEGRATION_HTTP_PORT=9090
      - UC_INTEGRATION_INTERFACE=0.0.0.0
      - PYTHONPATH=/app
    restart: unless-stopped
```

**Docker Run:**
```bash
docker run -d --name uc-intg-ezbeq --restart unless-stopped --network host -v $(pwd)/config:/config -e UC_CONFIG_HOME=/config -e UC_INTEGRATION_INTERFACE=0.0.0.0 -e UC_INTEGRATION_HTTP_PORT=9090 -e PYTHONPATH=/app ghcr.io/mase1981/uc-intg-ezbeq:latest
```

## Configuration

Setup is a **single screen**: enter your ezBEQ server's **IP address** and **port** (default `8080`). That's it - your DSP devices, their slots, and the BEQ catalogue are discovered automatically.

For each DSP device ezBEQ manages, the integration creates:

| Entity | Purpose |
|--------|---------|
| **Media player** (`<device> BEQ`) | Browse/search the catalogue and load a BEQ; shows the currently loaded BEQ in the selected slot. |
| **Select** (`<device> Slot`) | Pick which slot loads target. |
| **Sensors** (`<device> Slot N`) | One per slot, showing the loaded BEQ (or Empty). |

## Using the Integration

1. Add the **media player** to a page or Activity.
2. Use the **Slot** select to choose your target slot (miniDSP has ~4; HTP-1 has 1).
3. **Browse** (by Audio Type / Author / Year) or **Search** the catalogue and select a movie - its BEQ loads into the selected slot.
4. The **Sensors** reflect what's loaded in each slot; the media player's "now playing" shows the selected slot's BEQ.
5. To remove a filter, open the media browser and choose **Clear slot N**.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Cannot reach an ezBEQ server" | Verify the IP/port; open `http://<ezbeq-ip>:8080` in a browser to confirm ezBEQ is running. |
| "ezBEQ has no DSP devices configured" | Configure at least one device (miniDSP, HTP-1, ...) in ezBEQ's own config first. |
| Slot status not updating | The integration uses ezBEQ's WebSocket with a polling fallback; give it a few seconds, or check the ezBEQ server is reachable. |
| A load does nothing | Make sure the target slot (Select) is valid for that device and the DSP is online in ezBEQ. |

## Credits

- **Developer**: Meir Miyara
- **ezBEQ**: [3ll3d00d/ezbeq](https://github.com/3ll3d00d/ezbeq) and the BEQ community catalogue.
- **Unfolded Circle**: Remote 2/3 integration framework ([ucapi](https://github.com/unfoldedcircle/integration-python-library) / [ucapi-framework](https://github.com/JackJPowell/ucapi-framework)).

## License

Mozilla Public License 2.0 (MPL-2.0) - see the LICENSE file.

## Support & Community

- **GitHub Issues**: [Report bugs and request features](https://github.com/mase1981/uc-intg-ezbeq/issues)
- **UC Community Forum**: [General discussion and support](https://unfolded.community/)
- **Developer**: [Meir Miyara](https://www.linkedin.com/in/meirmiyara)

---

**Made with ❤️ for the Unfolded Circle Community**

**Thank You**: Meir Miyara
