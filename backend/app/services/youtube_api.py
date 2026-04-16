import os
import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import re
from typing import Dict, Any

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]

class YouTubeService:
    @staticmethod
    def get_creds_dir(channel_id: int, user_id: int, channel_name: str) -> Path:
        """Finds or creates the YouTube credentials directory within the channel's cache folder."""
        user_dir = Path("cache") / f"user_{user_id:04d}"
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # Search for folder starting with ID (e.g., "0005-")
        pattern = f"{channel_id:04d}-*"
        matches = list(user_dir.glob(pattern))
        
        if matches:
            channel_dir = matches[0]
        else:
            from app.core.utils import slugify
            channel_dir = user_dir / f"{channel_id:04d}-{slugify(channel_name)}"
            channel_dir.mkdir(parents=True, exist_ok=True)
            
        creds_dir = channel_dir / "youtube_credentials"
        creds_dir.mkdir(parents=True, exist_ok=True)
        return creds_dir

    def __init__(self, channel_id: int, user_id: int, channel_name: str):
        self.creds_dir = self.get_creds_dir(channel_id, user_id, channel_name)
        self.token_path = self.creds_dir / "token.json"
        self.secret_path = self.creds_dir / "client_secret.json"

    def get_credentials(self):
        creds = None
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            except Exception as e:
                print(f"Error loading credentials from {self.token_path}: {e}")
                return None
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    from google.auth.exceptions import RefreshError
                    creds.refresh(Request())
                    self.token_path.write_text(creds.to_json())
                except RefreshError:
                    print(f"Token expired or revoked for {self.creds_dir}. Deleting invalid token.")
                    if self.token_path.exists():
                        self.token_path.unlink()
                    return None
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    return None
            else:
                return None
        return creds

    def get_auth_url(self, redirect_uri: str):
        """Generates the authorization URL for Google OAuth."""
        if not self.secret_path.exists():
            # Check if there's a global one
            global_secret = YOUTUBE_CREDS_BASE / "client_secret.json"
            if global_secret.exists():
                 # Copy it to the current dir for the flow
                 import shutil
                 shutil.copy(global_secret, self.secret_path)
            else:
                raise FileNotFoundError(f"Missing client_secret.json in {self.creds_dir}")
        
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.secret_path), SCOPES, redirect_uri=redirect_uri
        )
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent' # Force consent to ensure we get a refresh token
        )
        return auth_url

    def finish_oauth(self, code: str, redirect_uri: str):
        """Exchanges the auth code for a token and saves it."""
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.secret_path), SCOPES, redirect_uri=redirect_uri
        )
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Save the credentials for the next run
        self.creds_dir.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(creds.to_json())
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

    def upload_video(self, video_path: Path, metadata: Dict[str, Any]):
        """Uploads a video to YouTube with the provided metadata."""
        creds = self.get_credentials()
        if not creds:
            raise RuntimeError("Not authenticated with YouTube")
        
        youtube = build("youtube", "v3", credentials=creds)
        
        # Sanitize tags: YouTube tags cannot contain certain characters like < > or be too long
        raw_tags = metadata.get("tags", "").split(",")
        clean_tags = []
        total_len = 0
        for tag in raw_tags:
            # Remove invalid chars and extra spaces
            t = tag.replace("?", "").replace("\u00bf", "").strip()
            if not t: continue
            if len(t) > 100: t = t[:97] + "..." # YouTube limit is 100 per tag
            
            if total_len + len(t) + 1 < 500: # Total limit is 500
                clean_tags.append(t)
                total_len += len(t) + 1
            else:
                break

        body = {
            "snippet": {
                "title": metadata.get("title", "Untitled Video"),
                "description": metadata.get("description", ""),
                "tags": clean_tags,
                "categoryId": metadata.get("category_id", "22")  # Default to People & Blogs
            },
            "status": {
                "privacyStatus": metadata.get("privacy_status", "private"),
                "selfDeclaredMadeForKids": False
            }
        }
        
        if metadata.get("publish_at"):
            body["status"]["publishAt"] = metadata["publish_at"]
            # Scheduled videos must be private or unlisted during upload
            if body["status"]["privacyStatus"] == "public":
                body["status"]["privacyStatus"] = "private"

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True
        )
        
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")
        
        return response

    def update_video_metadata(self, video_id: str, metadata: Dict[str, Any]):
        """Updates metadata for an existing YouTube video."""
        creds = self.get_credentials()
        if not creds:
            raise RuntimeError("Not authenticated with YouTube")
        
        youtube = build("youtube", "v3", credentials=creds)
        
        # Sanitize tags (reusing logic from upload_video)
        raw_tags = metadata.get("tags", "").split(",")
        clean_tags = []
        total_len = 0
        for tag in raw_tags:
            t = tag.replace("?", "").replace("\u00bf", "").strip()
            if not t: continue
            if len(t) > 100: t = t[:97] + "..."
            if total_len + len(t) + 1 < 500:
                clean_tags.append(t)
                total_len += len(t) + 1
            else:
                break

        body = {
            "id": video_id,
            "snippet": {
                "title": metadata.get("title"),
                "description": metadata.get("description"),
                "tags": clean_tags,
                "categoryId": metadata.get("category_id", "22")
            }
        }
        
        request = youtube.videos().update(
            part="snippet",
            body=body
        )
        response = request.execute()
        return response

    def set_thumbnail(self, video_id: str, thumbnail_path: Path):
        """Sets a custom thumbnail for a video."""
        creds = self.get_credentials()
        if not creds:
            raise RuntimeError("Not authenticated with YouTube")
        
        youtube = build("youtube", "v3", credentials=creds)
        
        request = youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_path))
        )
        response = request.execute()
        return response
