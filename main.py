import base64
from io import BytesIO
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.templating import Jinja2Templates
from pydantic import HttpUrl
from starlette.responses import HTMLResponse, StreamingResponse
from starlette.staticfiles import StaticFiles
from typing import Annotated
import qrcode
from PIL import Image
app = FastAPI()
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
async def about(request: Request):
    return templates.TemplateResponse(request=request, name="compresspdf.html")
