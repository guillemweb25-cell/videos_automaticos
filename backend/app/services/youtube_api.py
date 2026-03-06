import os
import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import re

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

YOUTUBE_CREDS_BASE = Path("/app/youtube_creds")

class YouTubeService:
    def __init__(self, creds_dir: str):
        self.creds_dir = YOUTUBE_CREDS_BASE / creds_dir
        self.creds_dir.mkdir(parents=True, exist_ok=True)
        self.token_path = self.creds_dir / "token.json"
        self.secret_path = self.creds_dir / "client_secret.json"

    def get_credentials(self):
        creds = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.token_path.write_text(creds.to_json())
            else:
                return None
        return creds

    def is_authenticated(self):
        return self.get_credentials() is not None

    async def get_channel_info(self):
        creds = self.get_credentials()
        if not creds:
            return None
        
        youtube = build("youtube", "v3", credentials=creds)
        request = youtube.channels().list(part="snippet,statistics", mine=True)
        response = request.execute()
        
        if response.get("items"):
            return response["items"][0]
        return None

    async def get_videos(self, max_results=50):
        creds = self.get_credentials()
        if not creds:
            return []
        
        youtube = build("youtube", "v3", credentials=creds)
        # First get uploads playlist ID
        ch_request = youtube.channels().list(part="contentDetails", mine=True)
        ch_response = ch_request.execute()
        
        uploads_playlist_id = ch_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        
        # Fetch videos from that playlist
        playlist_request = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=max_results
        )
        playlist_response = playlist_request.execute()
        
        items = playlist_response.get("items", [])
        if not items:
            return []
            
        video_ids = [item["contentDetails"]["videoId"] for item in items]
        
        # Enrich with duration and statistics
        video_request = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=",".join(video_ids)
        )
        video_response = video_request.execute()
        
        def parse_duration(duration_str):
            # PT1H2M3S
            match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
            if not match:
                return 0
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            return hours * 3600 + minutes * 60 + seconds

        videos = []
        for v in video_response.get("items", []):
            duration_sec = parse_duration(v["contentDetails"]["duration"])
            videos.append({
                "id": v["id"],
                "title": v["snippet"]["title"],
                "thumbnail": v["snippet"]["thumbnails"]["medium"]["url"],
                "published_at": v["snippet"]["publishedAt"],
                "duration_seconds": duration_sec,
                # User specifically asked for visits (views) in the shorts tab earlier
                "view_count": v["statistics"].get("viewCount", "0")
            })
        return videos
