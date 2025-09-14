from external import constants
import requests

def get_youtube_playlist_data(playlist_id, page_token=''):
    url = constants.YOUTUBE_PLAYLIST_API_GET_URL.format(f'&pageToken={page_token}', playlist_id, constants.YOUTUBE_API_KEY)
    response = requests.get(url)
    return response.json().get("nextPageToken", ""), response.json().get("items", [])

def get_youtube_video_data(video_id):
    url = constants.YOUTUBE_VIDEO_API_GET_URL.format(video_id, constants.YOUTUBE_API_KEY)
    response = requests.get(url)
    return response.json().get("items", [])
