# RunPod Test Recipe: Duix / HeyGem Digital Human

Date: 2026-06-27

Goal: test whether Duix/HeyGem can produce a publishable Kirill digital-human clip faster and better than the current MuseTalk Mac baseline.

## Why This Is Test #1

Duix/HeyGem is the strongest ready-system candidate because:

- it ships Docker images;
- it has a `docker-compose-5090.yml`;
- it exposes an HTTP API on port `8383`;
- the Electron client can likely be bypassed;
- it is marketed as full digital-human generation, not only lip-sync.

Local repo:

- `/Users/kirill/Documents/Projects/Duix-Avatar`
- `/Users/kirill/Documents/Projects/Comfyui_HeyGem`

Key files:

- `/Users/kirill/Documents/Projects/Duix-Avatar/deploy/docker-compose-5090.yml`
- `/Users/kirill/Documents/Projects/Duix-Avatar/src/main/api/f2f.js`
- `/Users/kirill/Documents/Projects/Duix-Avatar/src/main/service/video.js`
- `/Users/kirill/Documents/Projects/Duix-Avatar/src/main/config/config.js`
- `/Users/kirill/Documents/Projects/Comfyui_HeyGem/docker-compose-lite.yml`

## Known API Shape

From Duix Electron client:

```text
serviceUrl.face2face = http://127.0.0.1:8383/easy
POST /easy/submit
GET  /easy/query?code=<taskCode>
```

Payload from `src/main/service/video.js`:

```js
{
  audio_url: audioPath,
  video_url: videoPath
}
```

Need verify exact JSON response on RunPod.

## Input Assets

Use these first:

- avatar/source video: best clean Kirill source video if available;
- fallback source video: `research/avatar-lab/output/avatar-benchmark/musetalk-input/kirill-source-10s.mp4`;
- audio: `research/avatar-lab/output/avatar-benchmark/musetalk-input/kirill-own-voice-10s.wav`;
- output dir: `/workspace/outputs/duix-heygem-test/`.

Important:

- Current source video has baked subtitles, so it is only a technical test.
- For final quality we need a clean 20-60s avatar video.

## RunPod Setup Draft

Preferred GPU:

- RTX 5090
- fallback RTX 4090

Expected ports:

- `8383` for generation API.

Start Docker service using one of:

```bash
cd /workspace/Duix-Avatar/deploy
docker compose -f docker-compose-5090.yml up -d
```

or HeyGem lite:

```bash
cd /workspace/Comfyui_HeyGem
export HEGEM_FACE2FACE_DATA_PATH=/workspace/heygem-data
docker compose -f docker-compose-lite.yml up -d
```

Need adapt volume paths because repo compose files assume Windows-style `d:/duix_avatar_data/...`.

## API Smoke Test

After service starts:

```bash
curl -s http://127.0.0.1:8383/easy/health || true
curl -s http://127.0.0.1:8383/easy/docs || true
```

If no docs, inspect logs:

```bash
docker logs duix-avatar-gen-video --tail=200
docker logs heygem-gen-video --tail=200
```

Submit job, guessed shape:

```bash
curl -s -X POST http://127.0.0.1:8383/easy/submit \
  -H 'Content-Type: application/json' \
  -d '{
    "audio_url": "/workspace/inputs/kirill-own-voice-10s.wav",
    "video_url": "/workspace/inputs/kirill-source-10s.mp4"
  }'
```

Poll:

```bash
curl -s "http://127.0.0.1:8383/easy/query?code=<CODE>"
```

## Metrics To Record

- service cold start time;
- model load time;
- video duration;
- render wall time;
- output resolution;
- output file size;
- GPU memory used;
- GPU utilization;
- whether output has visible face drift;
- mouth sync quality;
- eyes stability;
- whether result is publishable.

## Pass / Fail

Pass:

- 10s clip is visibly better than MuseTalk Mac/MPS or at least comparable;
- no broken eyes/face dancing;
- API can be called without desktop UI;
- render speed can plausibly scale to 150 min/day.

Fail:

- requires manual desktop client;
- output is worse than MuseTalk;
- API is unstable or undocumented enough to slow us down;
- cold start/model download is too large for $10 testing.

## Next If Passes

1. Build `duix_batch_client.py`.
2. Wrap in RunPod pod lifecycle:
   - start;
   - upload inputs;
   - submit batch;
   - fetch outputs;
   - stop/delete.
3. Test 40 sec, 2-3 min, 10 min.

