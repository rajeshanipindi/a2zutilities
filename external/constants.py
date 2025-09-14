import os

YOUTUBE_API_KEY = os.environ.get('YOUTUBE_DATA_API_KEY')
YOUTUBE_PLAYLIST_API_GET_URL = 'https://youtube.googleapis.com/youtube/v3/playlistItems?part=snippet%2CcontentDetails{}&maxResults=50&playlistId={}&key={}'
YOUTUBE_VIDEO_API_GET_URL = 'https://youtube.googleapis.com/youtube/v3/videos?part=contentDetails&id={}&key={}'
