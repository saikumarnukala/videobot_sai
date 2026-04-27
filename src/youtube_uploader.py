import os
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import googleapiclient.http

class YouTubeUploader:
    def __init__(self, client_secrets_file="client_secrets.json"):
        self.scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        self.client_secrets_file = client_secrets_file
        self.api_service_name = "youtube"
        self.api_version = "v3"
        self.credentials = None

    def authenticate(self):
        if os.path.exists('token.json'):
            print("Found existing token.json, attempting to authenticate...")
            self.credentials = Credentials.from_authorized_user_file('token.json', self.scopes)

        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                print("Refreshing expired YouTube access token...")
                try:
                    self.credentials.refresh(Request())
                except Exception as e:
                    print(f"Token refresh failed: {e}")
                    self.credentials = None

            if not self.credentials or not self.credentials.valid:
                if not os.path.exists(self.client_secrets_file):
                    raise FileNotFoundError(
                        f"ERROR: {self.client_secrets_file} is missing! "
                        "You MUST download the JSON file from Google Cloud."
                    )
                # Detect headless / CI environment where browser flow cannot work
                if os.getenv("CI", "false").lower() in ("true", "1"):
                    raise RuntimeError(
                        "YouTube token is missing/invalid in CI. "
                        "Generate token.json locally with `python src/youtube_uploader.py` "
                        "and add it as a GitHub secret (YOUTUBE_TOKEN_JSON)."
                    )
                print("No existing token. Opening browser for first-time YouTube verification...")
                flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, self.scopes)
                self.credentials = flow.run_local_server(port=0)

            # Save credentials for next run
            with open('token.json', 'w') as token:
                token.write(self.credentials.to_json())

        return googleapiclient.discovery.build(
            self.api_service_name, self.api_version, credentials=self.credentials)

    def upload_short(self, file_path, title, description, category_id="22", privacy_status=None, tags=None):
        if privacy_status is None:
            privacy_status = (os.getenv("YOUTUBE_PRIVACY_STATUS") or os.getenv("YOUTUBE_PRIVACY") or "public").lower()
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"ERROR: Video file not found: {file_path}")
        if os.path.getsize(file_path) == 0:
            raise ValueError(f"ERROR: Video file is empty: {file_path}")
        if tags is None:
            tags = ["shorts", "shortsfeed", "viral"]
        youtube = self.authenticate()
        
        print(f"Uploading {file_path} to YouTube Shorts...")
        
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }
        
        # We use a resumable upload for better stability
        media = googleapiclient.http.MediaFileUpload(file_path, mimetype='video/mp4', chunksize=-1, resumable=True)
        
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        
        response = None
        try:
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"Uploaded {int(status.progress() * 100)}%")
                
        except googleapiclient.errors.HttpError as e:
            error_details = e.content.decode()
            if "quotaExceeded" in error_details:
                print("ERROR: YouTube API Quota Exceeded! You can only upload about 6 videos per day with default limits.")
            elif "insufficientPermissions" in error_details:
                print("ERROR: Insufficient Permissions. Your token might not have the 'youtube.upload' scope.")
            else:
                print(f"ERROR: YouTube API returned an error: {e}")
            raise e
        except Exception as e:
            print(f"ERROR: An unexpected error occurred during upload: {e}")
            raise e
        
        print(f"Upload Complete! Video published with ID: {response['id']}")
        return response['id']
