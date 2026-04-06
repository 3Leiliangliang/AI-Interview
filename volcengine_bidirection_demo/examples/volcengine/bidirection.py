#!/usr/bin/env python3
import argparse
import asyncio
import copy
import json
import logging
import uuid
from contextlib import nullcontext
from pathlib import Path

import sounddevice as sd
import websockets

from protocols import (
    EventType,
    MsgType,
    finish_connection,
    finish_session,
    receive_message,
    start_connection,
    start_session,
    task_request,
    wait_for_event,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_ENV_FILE = ROOT_DIR / ".env"
PCM_SAMPLE_WIDTH = 2


def get_resource_id(voice: str) -> str:
    if voice.startswith("saturn_") or voice.endswith("_uranus_bigtts"):
        return "seed-tts-2.0"
    if voice.startswith("S_"):
        return "volc.megatts.default"
    return "volc.service_type.10029"


def load_env_file(env_file: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_file.exists():
        return values

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


async def main():
    env_values = load_env_file(DEFAULT_ENV_FILE)
    default_appid = env_values.get("DOUBAO_VOICE_APP_ID", "")
    default_access_token = env_values.get("DOUBAO_VOICE_API_KEY", "")
    default_voice_type = env_values.get(
        "DOUBAO_VOICE_SPEAKER",
        "zh_male_m191_uranus_bigtts",
    )
    default_resource_id = env_values.get("DOUBAO_VOICE_RESOURCE_ID", "")

    parser = argparse.ArgumentParser()
    parser.add_argument("--appid", default=default_appid, help="APP ID")
    parser.add_argument("--access_token", default=default_access_token, help="Access Token")
    parser.add_argument("--resource_id", default=default_resource_id, help="Resource ID")
    parser.add_argument("--text", default="你好，这是一个最小化双向流式语音测试。", help="Text to convert")
    parser.add_argument("--voice_type", default=default_voice_type, help="Voice type")
    parser.add_argument("--encoding", default="pcm", help="Output file encoding")
    parser.add_argument("--output_dir", default="outputs", help="Directory for audio output")
    parser.add_argument("--char_delay_ms", type=float, default=5.0, help="Delay between characters")
    parser.add_argument(
        "--no-play",
        action="store_true",
        help="Disable real-time speaker playback",
    )
    parser.add_argument(
        "--endpoint",
        default="wss://openspeech.bytedance.com/api/v3/tts/bidirection",
        help="WebSocket endpoint URL",
    )

    args = parser.parse_args()
    if not args.appid or not args.access_token:
        raise SystemExit("Missing appid/access_token. Provide args or set DOUBAO_VOICE_APP_ID / DOUBAO_VOICE_API_KEY in root .env.")
    if not args.voice_type:
        raise SystemExit("Missing voice_type. Provide --voice_type or set DOUBAO_VOICE_SPEAKER in root .env.")
    if not args.no_play and args.encoding != "pcm":
        raise SystemExit("Real-time playback only supports --encoding pcm. Use --no-play to disable playback.")

    # Connect to server
    headers = {
        "X-Api-App-Key": args.appid,
        "X-Api-Access-Key": args.access_token,
        "X-Api-Resource-Id": (
            args.resource_id if args.resource_id else get_resource_id(args.voice_type)
        ),
        "X-Api-Connect-Id": str(uuid.uuid4()),
    }

    logger.info(f"Connecting to {args.endpoint} with headers: {headers}")
    websocket = await websockets.connect(
        args.endpoint, additional_headers=headers, max_size=10 * 1024 * 1024
    )
    logger.info(
        f"Connected to WebSocket server, Logid: {websocket.response.headers['x-tt-logid']}",
    )

    try:
        # Start connection
        await start_connection(websocket)
        await wait_for_event(
            websocket, MsgType.FullServerResponse, EventType.ConnectionStarted
        )

        playback_context = nullcontext()
        if not args.no_play:
            playback_context = sd.RawOutputStream(
                samplerate=24000,
                channels=1,
                dtype="int16",
                blocksize=0,
            )

        # Process each sentence
        sentences = args.text.split("。")
        audio_received = False

        with playback_context as output_stream:
            for i, sentence in enumerate(sentences):
                if not sentence:
                    continue

                # every session can have different parameters
                base_request = {
                    "user": {
                        "uid": str(uuid.uuid4()),
                    },
                    "namespace": "BidirectionalTTS",
                    "req_params": {
                        "speaker": args.voice_type,
                        "audio_params": {
                            "format": args.encoding,
                            "sample_rate": 24000,
                            "enable_timestamp": True,
                        },
                        "additions": json.dumps(
                            {
                                "disable_markdown_filter": False,
                            }
                        ),
                    },
                }

                # Start session
                start_session_request = copy.deepcopy(base_request)
                start_session_request["event"] = EventType.StartSession
                session_id = str(uuid.uuid4())
                await start_session(
                    websocket, json.dumps(start_session_request).encode(), session_id
                )
                await wait_for_event(
                    websocket, MsgType.FullServerResponse, EventType.SessionStarted
                )

                # Send characters one by one
                async def send_chars():
                    for char in sentence:
                        synthesis_request = copy.deepcopy(base_request)
                        synthesis_request["event"] = EventType.TaskRequest
                        synthesis_request["req_params"]["text"] = char
                        await task_request(
                            websocket, json.dumps(synthesis_request).encode(), session_id
                        )
                        await asyncio.sleep(args.char_delay_ms / 1000.0)

                    await finish_session(websocket, session_id)

                # Start sending characters in background
                send_task = asyncio.create_task(send_chars())

                # Receive audio data
                audio_data = bytearray()
                while True:
                    msg = await receive_message(websocket)

                    if msg.type == MsgType.FullServerResponse:
                        if msg.event == EventType.SessionFinished:
                            break
                    elif msg.type == MsgType.AudioOnlyServer:
                        if msg.payload:
                            audio_received = True
                            audio_data.extend(msg.payload)
                            if output_stream is not None:
                                playable_size = len(msg.payload) - (len(msg.payload) % PCM_SAMPLE_WIDTH)
                                if playable_size > 0:
                                    output_stream.write(msg.payload[:playable_size])
                        else:
                            logger.warning("Received empty audio chunk")
                    else:
                        raise RuntimeError(f"TTS conversion failed: {msg}")

                # Wait for send_chars to complete
                await send_task

                # Save audio file if we received any data
                if audio_data:
                    output_dir = Path(args.output_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    filename = output_dir / f"{args.voice_type}_session_{i}.{args.encoding}"
                    with open(filename, "wb") as f:
                        f.write(audio_data)
                    logger.info(f"Audio received: {len(audio_data)}, saved to {filename}")

        if not audio_received:
            raise RuntimeError("No audio data received")

    finally:
        # Finish connection
        await finish_connection(websocket)
        msg = await wait_for_event(
            websocket, MsgType.FullServerResponse, EventType.ConnectionFinished
        )
        await websocket.close()
        logger.info("Connection closed")


if __name__ == "__main__":
    asyncio.run(main())
