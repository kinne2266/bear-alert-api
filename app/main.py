import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal

import httpx
from fastapi import FastAPI, File, Form, UploadFile

# --- 設定（環境変数から読む） ---
WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")  # 未設定なら通知しない（テストやCIのため）
DB_PATH = os.getenv("DB_PATH", "events.db")
SNAP_DIR = Path(os.getenv("SNAP_DIR", "snapshots"))
SNAP_DIR.mkdir(parents=True, exist_ok=True)

JST = timezone(timedelta(hours=9))
NOTIFY_LEVELS = {"警戒", "緊急"}  # 「注意」は記録だけ

SCHEMA = """CREATE TABLE IF NOT EXISTS events (
    ts REAL, camera_id TEXT, zone TEXT, level TEXT,
    track_id INTEGER, confidence REAL, snapshot TEXT, notified INTEGER)"""

app = FastAPI(title="Bear Alert API")


def connect():
    """データベースにつなぎ、表がなければ作る"""
    con = sqlite3.connect(DB_PATH)
    con.execute(SCHEMA)
    return con


async def notify(level, zone, camera_id, confidence, ts, name, image):
    """Discordに静止画つきで通知する。失敗したら False を返す"""
    when = datetime.fromtimestamp(ts, JST).strftime("%H:%M")
    msg = f"【{level}】{when} {camera_id}の{zone}で熊を検出（信頼度 {confidence:.2f}）"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(WEBHOOK, data={"content": msg},
                                    files={"file": (name, image, "image/jpeg")})
            res.raise_for_status()
        return True
    except httpx.HTTPError:
        return False


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/events")
async def create_event(
    camera_id: Annotated[str, Form()],
    zone: Annotated[str, Form()],
    level: Annotated[Literal["注意", "警戒", "緊急"], Form()],
    track_id: Annotated[int, Form()],
    confidence: Annotated[float, Form()],
    snapshot: Annotated[UploadFile, File()],
):
    ts = time.time()
    image = await snapshot.read()
    name = f"{camera_id}_{int(ts)}_{track_id}.jpg"
    (SNAP_DIR / name).write_bytes(image)

    notified = False
    if level in NOTIFY_LEVELS and WEBHOOK:
        notified = await notify(level, zone, camera_id, confidence, ts, name, image)

    con = connect()
    try:
        con.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (ts, camera_id, zone, level, track_id, confidence, name, int(notified)))
        con.commit()
    finally:
        con.close()
    return {"status": "recorded", "notified": notified}


@app.get("/events")
def list_events(limit: int = 50):
    con = connect()
    try:
        rows = con.execute(
            "SELECT ts, camera_id, zone, level, confidence, notified "
            "FROM events ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    finally:
        con.close()
    keys = ["ts", "camera_id", "zone", "level", "confidence", "notified"]
    return [dict(zip(keys, row)) for row in rows]