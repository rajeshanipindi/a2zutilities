import base64
import json
from datetime import timedelta
from io import BytesIO
from typing import Annotated
from urllib.parse import urlparse, parse_qs

import isodate
import qrcode
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import HttpUrl
from starlette.middleware.base import BaseHTTPMiddleware
from PIL import Image, UnidentifiedImageError

# Local application imports
from external import utilities as utils

# --- Constants ---
ERROR_MSG_YT_PLAYLIST = (
    "Something went wrong. Please ensure your playlist URL is valid and public."
)
ERROR_MSG_IMG_COMPRESS = (
    "Something went wrong. Please ensure you are uploading a valid JPEG/PNG file."
)
ERROR_MSG_JSON_BEAUTIFY = (
    "Something went wrong. Please ensure you are providing valid JSON data."
)


# --- Middleware ---
class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    """
    A middleware to correctly handle URL schemes when running behind a reverse proxy.
    This reads the 'x-forwarded-proto' header.
    """
    async def dispatch(self, request: Request, call_next):
        """Sets the request scheme based on the 'x-forwarded-proto' header."""
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto:
            request.scope["scheme"] = forwarded_proto
        response = await call_next(request)
        return response


# --- Application Setup ---
app = FastAPI()
app.add_middleware(ProxyHeadersMiddleware)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# --- Helper Functions for YouTube Playlist ---
def _fetch_all_video_ids(playlist_id: str) -> list[str]:
    """Fetches all video IDs from a YouTube playlist, handling pagination."""
    video_ids = []
    next_page_token, item_list = utils.get_youtube_playlist_data(playlist_id)
    video_ids.extend(item["contentDetails"]["videoId"] for item in item_list)

    while next_page_token:
        next_page_token, item_list = utils.get_youtube_playlist_data(
            playlist_id, next_page_token
        )
        video_ids.extend(item["contentDetails"]["videoId"] for item in item_list)
    return video_ids, item_list


def _calculate_total_duration(video_ids: list[str]) -> timedelta:
    """Calculates the total duration of a list of YouTube videos."""
    video_durations = []
    for video_id in video_ids:
        video_data = utils.get_youtube_video_data(video_id)
        if video_data:
            duration_iso = video_data[0]["contentDetails"]["duration"]
            video_durations.append(isodate.parse_duration(duration_iso))
    return sum(video_durations, timedelta())


# --- General Endpoints ---
@app.get("/", response_class=HTMLResponse)
async def get_root(request: Request):
    """Serves the main index page."""
    return templates.TemplateResponse(request=request, name="index.html")


# --- QR Code Generator Endpoints ---
@app.get("/generateqr", response_class=HTMLResponse)
async def get_generate_qr_form(request: Request):
    """Serves the QR code generation form page."""
    return templates.TemplateResponse(request=request, name="generateqr.html")


@app.post("/generateqr", response_class=HTMLResponse)
async def handle_generate_qr_form(request: Request, url: Annotated[HttpUrl, Form()]):
    """
    Generates a QR code from a URL. Returns an image directly or a page
    containing the image, based on the request's 'Accept' header.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(str(url))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="transparent")

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    accept_header = request.headers.get("accept", "")
    if "text/html" not in accept_header and "image/" in accept_header:
        return StreamingResponse(buf, media_type="image/png")

    image_bytes = buf.getvalue()
    encoded_string = base64.b64encode(image_bytes).decode("utf-8")
    image_data_uri = f"data:image/png;base64,{encoded_string}"
    return templates.TemplateResponse(
        request=request,
        name="generateqr.html",
        context={"generated_image": image_data_uri},
    )


# --- YouTube Playlist Endpoints ---
@app.get("/ytplaylist", response_class=HTMLResponse)
async def get_yt_playlist_form(request: Request):
    """Serves the YouTube playlist duration calculator form page."""
    return templates.TemplateResponse(request=request, name="ytplaylist.html")


@app.post("/ytplaylist", response_class=HTMLResponse)
async def handle_yt_playlist_form(request: Request, url: Annotated[HttpUrl, Form()]):
    """
    Calculates the total duration and video count of a YouTube playlist.
    """
    ytplaylist_response = {"error": ""}
    try:
        parsed_url = urlparse(str(url))
        query_params = parse_qs(parsed_url.query)
        playlist_id = query_params.get("list", [None])[0]

        if not playlist_id:
            raise ValueError("Invalid YouTube playlist URL: 'list' parameter missing.")

        video_ids, item_list = _fetch_all_video_ids(playlist_id)
        total_duration = _calculate_total_duration(video_ids)

        thumbnail = ""
        video_creator = ""
        if item_list:
            thumbnail = item_list[0]["snippet"]["thumbnails"]["high"]["url"]
            video_creator = item_list[0]["snippet"]["channelTitle"]

        ytplaylist_response["result"] = {
            "total_duration": total_duration,
            "video_count": len(video_ids),
            "thumbnail": thumbnail,
            "video_creator": video_creator,
        }
    except (ValueError, IndexError, KeyError):
        ytplaylist_response["error"] = ERROR_MSG_YT_PLAYLIST

    return templates.TemplateResponse(
        request=request, name="ytplaylist.html", context=ytplaylist_response
    )


# --- Image Compressor Endpoints ---
@app.get("/compressimg", response_class=HTMLResponse)
async def get_compress_image_form(request: Request):
    """Serves the image compression form page."""
    return templates.TemplateResponse(request=request, name="compressimg.html")


@app.post("/compressimg", response_class=HTMLResponse)
async def handle_compress_image_form(
    request: Request, file: UploadFile = File(...), compression_ratio: int = Form(...)
):
    """Compresses an uploaded JPEG or PNG image."""
    compression_response = {"error": ""}
    try:
        with Image.open(file.file) as image_handler:
            output_buffer = BytesIO()
            file_format = "PNG" if file.content_type == "image/png" else "JPEG"
            image_handler.save(
                output_buffer, format=file_format, optimize=True, quality=compression_ratio
            )

        image_bytes = output_buffer.getvalue()
        encoded_string = base64.b64encode(image_bytes).decode("utf-8")
        media_type = "image/png" if file_format == "PNG" else "image/jpeg"
        compressed_image_uri = f"data:{media_type};base64,{encoded_string}"

        compression_response["result"] = {
            "actual_size": round((file.size or 0) / 1024, 2),
            "compressed_size": round(output_buffer.tell() / 1024, 2),
            "compressed_image_uri": compressed_image_uri,
        }

    except (IOError, UnidentifiedImageError):
        compression_response["error"] = ERROR_MSG_IMG_COMPRESS

    return templates.TemplateResponse(
        request=request, name="compressimg.html", context=compression_response
    )


# --- PDF Compressor Endpoint ---
@app.get("/compresspdf", response_class=HTMLResponse)
async def get_compress_pdf_page(request: Request):
    """Serves the PDF compression page."""
    return templates.TemplateResponse(request=request, name="compresspdf.html")


# --- JSON Beautifier Endpoints ---
@app.get("/beautifyjson", response_class=HTMLResponse)
async def get_beautify_json_form(request: Request):
    """Serves the JSON beautifier form page."""
    return templates.TemplateResponse(request=request, name="beautifyjson.html")


@app.post("/beautifyjson", response_class=HTMLResponse)
async def handle_beautify_json_form(request: Request, json_data: str = Form(...)):
    """Formats a string of JSON data with proper indentation."""
    beautify_response = {
        "original_json": json_data,
        "formatted_json": "",
        "error": None,
    }
    try:
        parsed_data = json.loads(json_data)
        formatted_json = json.dumps(parsed_data, indent=4)
        beautify_response["formatted_json"] = formatted_json
    except json.JSONDecodeError:
        beautify_response["error"] = ERROR_MSG_JSON_BEAUTIFY

    return templates.TemplateResponse(
        request=request, name="beautifyjson.html", context=beautify_response
    )
