from .data_queue import global_audio_data_queue, reording_pause_flag
import pyaudio
import threading
import time

# 设置音频参数
RATE = 16000
SILENCE_DURATION = 2.0  # 设置语音识别的阈值
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1

class RecordingService:
    def __init__(self):
        pass
        
    def run(self):
         # 初始化PyAudio
        pyaudio_instance = None
        stream = None

        try:
            if reording_pause_flag.is_set():
                return
            
            pyaudio_instance = pyaudio.PyAudio()
        
                # 打开音频流
            stream = pyaudio_instance.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK,
                    stream_callback=self.audio_callback
                )
            stream.start_stream()
            while True:
                if reording_pause_flag.is_set():
                    break
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            if pyaudio_instance:
                pyaudio_instance.terminate()
        
    def audio_callback(self, in_data, frame_count, time_info, status):
        """音频回调函数，将音频数据放入队列"""
        if not reording_pause_flag.is_set():
            global_audio_data_queue.put(in_data)
        return (in_data, pyaudio.paContinue)
