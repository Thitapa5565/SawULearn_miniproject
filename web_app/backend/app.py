"""Standalone API for the latest combined-expert SawULearn submission."""
from contextlib import asynccontextmanager
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from .inference import ModelService, TRAINING_ROOT

WEB_ROOT = Path(__file__).resolve().parents[1]
service = ModelService()
MODEL_RUN = service.active_run
EXAMPLES = json.loads((WEB_ROOT/'backend/examples.json').read_text(encoding='utf-8'))
ASSETS = {example['id']+'.jpg': WEB_ROOT/'public/examples'/(example['id']+'.jpg') for example in EXAMPLES}
LESSONS = [{
    'id': 'dltv-sawu',
    'title': 'การไล่นิ้ว การกดสาย การใช้คันชักซออู้ (1)',
    'subtitle': 'บทเรียนซออู้จาก DLTV · ดูการสาธิตแล้วกลับมาฝึกท่านั่งและคันชักพร้อมกัน',
    'source': 'DLTV มูลนิธิการศึกษาทางไกลผ่านดาวเทียม',
    'source_url': 'https://dltv.ac.th/teachplan/episode/58966',
    'video': 'https://cdn-vod.dltv.ac.th/vod/upload/data/videos/26/video_65653-v-202304181559.mp4/master.m3u8',
    'video_type': 'hls',
}]


@asynccontextmanager
async def lifespan(app):
    yield
    service.close()


app = FastAPI(title='SawULearn', lifespan=lifespan)


@app.get('/api/health')
def health():
    return {'status': 'ready', 'model_run': MODEL_RUN,
            'targets': service.posture['targets'], 'combined_experts': True}


@app.get('/api/examples')
def examples():
    return EXAMPLES


@app.get('/api/lessons')
def lessons():
    return LESSONS


@app.get('/api/models')
def models():
    report = TRAINING_ROOT/'reports'/MODEL_RUN
    return {'run': MODEL_RUN, 'deployment': 'combined_experts_v1',
            'summary': json.loads((report/'training_record.json').read_text(encoding='utf-8')),
            'selection': json.loads((report/'selection.json').read_text(encoding='utf-8')),
            'validation': json.loads((report/'val/results.json').read_text(encoding='utf-8')),
            'test': json.loads((report/'test/results.json').read_text(encoding='utf-8')),
            'posture_joint': json.loads((report/'test/posture_joint_metrics.json').read_text(encoding='utf-8')),
            'runtime_policy': {'initial_grip_guard': service.body_grip['guard'],
                               'initial_grip_window_s': 2, 'initial_grip_settle_s': 10,
                               'bow_error_range_margin_fraction': .2,
                               'note': 'Held-out scores are raw predictions. The website also applies quality guards.'}}


@app.post('/api/analyze/posture')
@app.post('/api/analyze/hands')
@app.post('/api/analyze/guided')
@app.post('/api/analyze/body-grip')
async def analyze(request: Request):
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 4_000_000:
            raise HTTPException(413, 'ภาพมีขนาดใหญ่เกินไป')
        chunks.append(chunk)
    image = b''.join(chunks)
    try:
        if request.url.path in ('/api/analyze/body-grip', '/api/analyze/guided'):
            hands = request.headers.get('X-Include-Hands', '1')
            initial = request.headers.get('X-Include-Initial-Grip', '1')
            level = request.headers.get('X-Include-Bow-Level', '1')
            if any(value not in ('0', '1') for value in [hands, initial, level]):
                raise ValueError('ตัวเลือกตรวจไม่ถูกต้อง')
            if request.url.path.endswith('/body-grip'):
                return await run_in_threadpool(service.analyze_body_grip, image,
                    include_hands=hands=='1', include_initial_grip=initial=='1', include_bow_level=level=='1')
            return await run_in_threadpool(service.analyze_guided, image, include_hands=hands=='1')
        operation = service.analyze_hands if request.url.path.endswith('/hands') else service.analyze_image
        return await run_in_threadpool(operation, image)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.get('/media/lessons/{filename}')
def lesson_media(filename: str):
    path = ASSETS.get(filename)
    if path is None or not path.is_file():
        raise HTTPException(404, 'ไม่พบตัวอย่างนี้')
    return FileResponse(path)


if (WEB_ROOT/'dist').is_dir():
    app.mount('/', StaticFiles(directory=WEB_ROOT/'dist', html=True), name='frontend')
