import json
import time
import io
from typing import Iterator
import threading
import wave

import requests
import pyaudio
from pydub import AudioSegment
from services.data_queue import global_text_result_queue, reording_pause_flag


class TTS:
    def __init__(self, group_id, api_key):
        self.group_id = group_id
        self.api_key = api_key
        self.url = f"https://api.minimax.chat/v1/t2a_v2?GroupId={group_id}"
        self.headers = {
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json',
            'authorization': "Bearer " + api_key,
        }
        # PyAudio初始化
        self.p = pyaudio.PyAudio()
        # 播放缓冲队列
        self.audio_buffer = b""
        self.buffer_lock = threading.Lock()
        # 播放线程标志
        self.is_playing = False
        # 播放结束事件
        self.play_finished = threading.Event()
        
    def say(self, text, format="pcm"):
        """
        流式合成并播放文本对应的语音
        
        Args:
            text: 要合成的文本
            format: 音频格式，'pcm'或'mp3'
        """
        # 重置播放状态
        self.audio_buffer = b""
        self.is_playing = True
        self.play_finished.clear()
        
        # 启动播放线程
        play_thread = threading.Thread(target=self._play_stream, args=(format,))
        play_thread.daemon = True
        reording_pause_flag.set()
        play_thread.start()
        
        # 获取音频流并添加到缓冲区
        self._stream_audio_data(text, format)
        
        # 标记结束并等待播放完成
        self.is_playing = False
        self.play_finished.wait()
        reording_pause_flag.clear()
    def _stream_audio_data(self, text, format):
        """流式获取音频数据并添加到缓冲区"""
        audio_chunk_iterator = self.call_tts_stream(text, format)
        
        for chunk in audio_chunk_iterator:
            if chunk is not None and chunk != '\n':
                decoded_data = bytes.fromhex(chunk)
                
                # 如果是MP3格式，需要转换为PCM
                if format == "mp3":
                    try:
                        sound = AudioSegment.from_mp3(io.BytesIO(decoded_data))
                        pcm_data = sound.raw_data
                        with self.buffer_lock:
                            self.audio_buffer += pcm_data
                    except Exception as e:
                        print(f"MP3解码错误: {e}")
                else:
                    # PCM格式直接添加到缓冲区
                    with self.buffer_lock:
                        self.audio_buffer += decoded_data
                        
    def _play_stream(self, format):
        """播放流式音频线程"""
        # 音频流参数
        sample_rate = 16000 if format == "pcm" else 44100  # MP3默认采样率
        channels = 1  # 单声道
        sample_width = 2  # 16位采样
        
        # 打开音频流
        stream = self.p.open(
            format=self.p.get_format_from_width(sample_width),
            channels=channels,
            rate=sample_rate,
            output=True,
            frames_per_buffer=1024
        )
        
        # 流式播放
        try:
            while self.is_playing or len(self.audio_buffer) > 0:
                with self.buffer_lock:
                    # 取出一块数据播放
                    chunk_size = min(1024 * 4, len(self.audio_buffer))
                    if chunk_size > 0:
                        chunk = self.audio_buffer[:chunk_size]
                        self.audio_buffer = self.audio_buffer[chunk_size:]
                    else:
                        chunk = None
                
                if chunk:
                    stream.write(chunk)
                else:
                    # 没有数据时短暂等待
                    time.sleep(0.01)
        finally:
            # 关闭流
            stream.stop_stream()
            stream.close()
            self.play_finished.set()
        
    def call_tts_stream(self, text, format="pcm"):
        """调用MiniMax API获取语音流"""
        audio_format = "pcm" if format == "pcm" else "mp3"
        sample_rate = 16000 if format == "pcm" else 32000
        
        payload = {
            "model": "speech-01-hd",
            "text": text,
            "stream": True,
            "timber_weights": [
                {
                "voice_id": "female-yujie",
                "weight": 1
                }
            ],
            "voice_setting": {
                "voice_id": "",
                "speed": 1,
                "pitch": 0,
                "vol": 1,
                "latex_read": False
            },
            "audio_setting": {
                "sample_rate": sample_rate,
                "bitrate": 128000,
                "format": audio_format
            },
            "language_boost": "auto"
        }
        
        response = requests.post(self.url, stream=True, headers=self.headers, json=payload)
        for chunk in (response.raw):
            if chunk:
                if chunk[:5] == b'data:':
                    data = json.loads(chunk[5:])
                    if "data" in data and "extra_info" not in data:
                        if "audio" in data["data"]:
                            audio = data["data"]['audio']
                            yield audio
    def run_forever(self, stop_event):
        while not stop_event.is_set():
            if global_text_result_queue.empty():
                continue
            text = global_text_result_queue.get()
            self.say(text)
            time.sleep(0.01)
