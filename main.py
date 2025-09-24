from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse
from pytube import YouTube
from moviepy.editor import VideoFileClip
from supabase import create_client
import os, uuid

# --- Supabase config ---
SUPABASE_URL = "https://hzfowzvdowjgtxpwiycq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh6Zm93enZkb3dqZ3R4cHdpeWNxIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODcyNTA5NSwiZXhwIjoyMDc0MzAxMDk1fQ.prtjQQY4LBDYRsIiCjiRdqImTJLqjBPBvRMTITgoCAo"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
BUCKET_NAME = "shorts"

# --- Folders ---
os.makedirs("downloads", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
os.makedirs("clips", exist_ok=True)

app = FastAPI()

# --- Helper: create vertical shorts ---
def make_short_clips(video_path, duration=60):
    clips_list = []
    video = VideoFileClip(video_path)
    total = int(video.duration)
    step = max(duration, total // 5)  # split into roughly 5 clips

    for i in range(0, total, step):
        end = min(i + duration, total)
        subclip = video.subclip(i, end)

        # Resize to vertical 9:16
        h, w = subclip.h, subclip.w
        target_w = int(h * 9 / 16)
        x_center = w // 2
        x1 = max(0, x_center - target_w // 2)
        x2 = min(w, x_center + target_w // 2)
        vertical = subclip.crop(x1=x1, y1=0, x2=x2, y2=h)

        filename = f"clips/{uuid.uuid4().hex}.mp4"
        vertical.write_videofile(filename, codec="libx264", audio_codec="aac", logger=None)
        clips_list.append(filename)
    video.close()
    return clips_list

# --- Helper: upload to Supabase ---
def upload_to_supabase(file_path):
    file_name = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        supabase.storage.from_(BUCKET_NAME).upload(file_name, f, {"cacheControl": "3600", "upsert": True})
    url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_name)
    return url

# --- Endpoint: process YouTube ---
@app.post("/youtube")
def process_youtube(url: str = Form(...)):
    yt = YouTube(url)
    stream = yt.streams.filter(progressive=True, file_extension="mp4").first()
    file_path = stream.download(output_path="downloads", filename=f"{uuid.uuid4().hex}.mp4")
    clips = make_short_clips(file_path)
    urls = [upload_to_supabase(c) for c in clips]
    return JSONResponse({"clips": urls})

# --- Endpoint: upload local video ---
@app.post("/upload")
async def upload_video(file: UploadFile):
    file_path = f"uploads/{uuid.uuid4().hex}_{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())
    clips = make_short_clips(file_path)
    urls = [upload_to_supabase(c) for c in clips]
    return JSONResponse({"clips": urls})
