#!/usr/bin/env python3
"""Playlist Helper — Web Server launcher.

Starts the API server on port 9999, accessible at http://localhost:9999.
Also accessible via Tailscale at http://<tailscale-ip>:9999.
"""

from server.main import main

if __name__ == "__main__":
    main()
