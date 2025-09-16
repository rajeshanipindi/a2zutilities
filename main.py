import json
from io import BytesIO
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.templating import Jinja2Templates
from pydantic import HttpUrl
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse, StreamingResponse
from starlette.staticfiles import StaticFiles
from typing import Annotated
from PIL import Image
from external import utilities as utils
from datetime import timedelta
from urllib.parse import urlparse, parse_qs
import base64, qrcode, isodate

class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto:
            request.scope["scheme"] = forwarded_proto

        response = await call_next(request)
        return response

app = FastAPI()
app.add_middleware(ProxyHeadersMiddleware)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/generateqr", response_class=HTMLResponse)
async def generate_qr(request: Request):
    return templates.TemplateResponse(request=request, name="generateqr.html")

@app.post("/generateqr", response_class=HTMLResponse)
async def generate_qr(request: Request, url : Annotated[HttpUrl, Form()]):
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
    print(accept_header)
    if "text/html" not in accept_header and "image/" in accept_header:
        return StreamingResponse(buf, media_type="image/png")
    else:
        image_bytes = buf.getvalue()
        encoded_string = base64.b64encode(image_bytes).decode('utf-8')
        image_data_uri = f"data:image/png;base64,{encoded_string}"
        return templates.TemplateResponse(request=request, name="generateqr.html", context={"generated_image": image_data_uri})

@app.get("/ytplaylist", response_class=HTMLResponse)
async def youtube_playlist(request: Request):
    return templates.TemplateResponse(request=request, name="ytplaylist.html")

@app.post("/ytplaylist", response_class=HTMLResponse)
async def youtube_playlist(request: Request, url: Annotated[HttpUrl, Form()]):
    parsed_url = urlparse(str(url))
    query_params = parse_qs(parsed_url.query)
    playlist_id = query_params.get('list', [None])[0]
    ytplaylist_response = {"error": ""}
    try:
        if not playlist_id:
            raise Exception
        video_ids = []
        next_page_token, item_list = utils.get_youtube_playlist_data(playlist_id)
        video_ids.extend([item["contentDetails"]["videoId"] for item in item_list])
        thumbnail = ""
        video_creator = ""
        if item_list:
            thumbnail = item_list[0]["snippet"]["thumbnails"]["high"]["url"]
            video_creator = item_list[0]["snippet"]["channelTitle"]
        while next_page_token:
            next_page_token, item_list = utils.get_youtube_playlist_data(playlist_id, next_page_token)
            video_ids.extend([item["contentDetails"]["videoId"] for item in item_list])
        video_count = len(video_ids)
        video_durations = []
        for video_id in video_ids:
            video_data = utils.get_youtube_video_data(video_id)
            if video_data:
                duration = video_data[0]["contentDetails"]["duration"]
                video_durations.append(duration)
        parsed_durations = [isodate.parse_duration(duration) for duration in video_durations]
        total_duration = sum(parsed_durations, timedelta())
        ytplaylist_response["result"] = {
            "total_duration": total_duration,
            "video_count": video_count,
            "thumbnail": thumbnail,
            "video_creator": video_creator,
        }
    except Exception as e:
        ytplaylist_response["error"] = "Something went wrong. Please try again later. (Please make sure your input playlist url is valid)"
    return templates.TemplateResponse(request=request, name="ytplaylist.html", context=ytplaylist_response)

@app.get("/compressimg", response_class=HTMLResponse)
async def compress_image(request: Request):
    return templates.TemplateResponse(request=request, name="compressimg.html")

@app.post("/compressimg", response_class=HTMLResponse)
async def compress_image(request: Request, file: UploadFile = File(...), compression_ratio: int = Form(...)):
    compression_response = {'error': ""}
    try:
        image_handler = Image.open(file.file)
        output_buffer = BytesIO()
        compressed_filename = file.filename+'_compressed.jpg'
        if file.content_type == "image/png":
            image_handler.save(output_buffer, format='PNG', optimize=True, quality=compression_ratio)
        else:
            image_handler.save(output_buffer, format='JPEG', optimize=True, quality=compression_ratio)
        image_bytes = output_buffer.getvalue()
        encoded_string = base64.b64encode(image_bytes).decode('utf-8')
        compressed_image_uri = f"data:image/png;base64,{encoded_string}" if file.content_type == "image/png" else f"data:image/jpeg;base64,{encoded_string}"
        compression_response["result"] = {
            "actual_size": round(file.size / 1024, 2),
            "compressed_size": round(output_buffer.tell() / 1024, 2),
            "compressed_image_uri": compressed_image_uri,
        }

    except Exception as e:
        compression_response["error"] = "Something went wrong, Please ensure you are uploading a valid JPEG/PNG file"
    return templates.TemplateResponse(request=request, name="compressimg.html", context=compression_response)

@app.get("/compresspdf", response_class=HTMLResponse)
async def compress_pdf(request: Request):
    return templates.TemplateResponse(request=request, name="compresspdf.html")

@app.get("/beautifyjson", response_class=HTMLResponse)
async def beautify_json(request: Request):
    return templates.TemplateResponse(request=request, name="beautifyjson.html")

@app.post("/beautifyjson", response_class=HTMLResponse)
async def beautify_json(request: Request, json_data: str = Form(...)):
    beautify_response = {
        "original_json": json_data,
        "formatted_json": "",
        "error": None
    }
    try:
        data = json.loads(json_data)
        formatted_json = json.dumps(data, indent=4)
        beautify_response["formatted_json"] = formatted_json
    except Exception as e:
        beautify_response["error"] = "Something went wrong, Please ensure you are providing valid JSON data"
    return templates.TemplateResponse(request=request, name="beautifyjson.html", context=beautify_response)