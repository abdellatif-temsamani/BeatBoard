"""Constants for Spotify integration."""

from __future__ import annotations

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
DEFAULT_SCOPES = "user-read-currently-playing user-read-playback-state"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"
SPOTIFY_DEALER_WS_URL = "wss://dealer.spotify.com/?access_token={token}"
SPOTIFY_CURRENTLY_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"
# No hardcoded credentials – must be provided via config.yaml or env
DEFAULT_CLIENT_ID = ""
DEFAULT_CLIENT_SECRET = ""

# Sentinel for 401 Unauthorized – distinguishes auth failure from "nothing playing"
_UNAUTHORIZED: object = object()
