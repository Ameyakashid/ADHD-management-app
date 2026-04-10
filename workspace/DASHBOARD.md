# Dashboard Setup — Fire Tablet

The status dashboard runs as a web page served by the bot's Mac host. The Fire Tablet displays it in Silk browser as an always-on ambient screen.

## URL

```
http://<mac-ip>:8085
```

Replace `<mac-ip>` with the Mac's local network IP (find it via System Settings > Network, or `ifconfig en0`). Default port is 8085 — change via `DASHBOARD_PORT` in `.env`.

## Fire Tablet Setup

1. **Connect to the same Wi-Fi** as the Mac running the bot
2. **Open Silk browser** and navigate to `http://<mac-ip>:8085`
3. **Bookmark the page** for quick access

## Keep Screen Awake

Settings > Display > Screen Timeout > set to the longest option available. For always-on:

1. Settings > Device Options > tap "Serial Number" 7 times to enable Developer Options
2. Settings > Developer Options > enable "Stay Awake" (screen stays on while charging)
3. Keep the tablet plugged in

## Fullscreen Mode

In Silk browser, tap the menu (three dots) and select "Full Screen" or "Add to Home Screen" to launch without the browser chrome.

## What the Dashboard Shows

- **Cognitive state** — colored banner at top (green=baseline, blue=focus, purple=hyperfocus, orange=avoidance, red=overwhelm, pink=RSD)
- **Buffer gauges** — fill bars for each tracked obligation
- **Active tasks** — current non-done tasks with due dates
- **Check-in schedule** — today's check-in times and status
- **Activity feed** — recent completions, buffer changes, fired check-ins

The page auto-refreshes every 30 seconds by default. Adjust via `DASHBOARD_REFRESH_INTERVAL` in `.env` (value in milliseconds).

## Troubleshooting

- **Page won't load**: Verify the Mac IP and port. Ensure `python start.py` is running. Check that the Mac firewall allows incoming connections on the dashboard port.
- **Data sections empty**: Normal on first start before any tasks, buffers, or check-ins are created.
- **CONNECTION ERROR banner**: The dashboard lost contact with the server. It will recover automatically on the next refresh cycle.
