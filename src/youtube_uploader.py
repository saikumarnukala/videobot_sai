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
        # The file token.json stores the user's access and refresh tokens.
        if os.path.exists('token.json'):
            print("Found existing token.json, attempting to authenticate...")
            self.credentials = Credentials.from_authorized_user_file('token.json', self.scopes)
        
        # If there are no (valid) credentials available, let the user log in.
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                print("Refreshing expired YouTube access token...")
                self.credentials.refresh(Request())
            else:
                if not os.path.exists(self.client_secrets_file):
                    raise FileNotFoundError(f"ERROR: {self.client_secrets_file} is missing! You MUST download the JSON file from Google Cloud.")
                
                print(f"No existing token. Opening browser for first-time YouTube verification...")
                flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, self.scopes)
                self.credentials = flow.run_local_server(port=0)
                
            # Save the credentials for the next run (so the automation works seamlessly forever after)
            with open('token.json', 'w') as token:
                token.write(self.credentials.to_json())
                
        return googleapiclient.discovery.build(
            self.api_service_name, self.api_version, credentials=self.credentials)

    def upload_short(self, file_path, title, description, category_id="22", privacy_status="private"):
        youtube = self.authenticate()
        
        print(f"Uploading {file_path} to YouTube Shorts...")
        
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["shorts", "shortsfeed", "viral"],
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
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")
                
        print(f"Upload Complete! Video published with ID: {response['id']}")
        return response['id']
