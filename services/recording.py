from .data_queue import global_audio_data_queue
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
        self.is_paused = False
        self.stream = None
        self.pyaudio_instance = None
        
    def async_run(self):
         # 初始化PyAudio
        self.pyaudio_instance = pyaudio.PyAudio()
    
        # 打开音频流
        self.stream = self.pyaudio_instance.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
            stream_callback=self.audio_callback
        )
        self.stream.start_stream()
        
    def close(self):
        self.stream.stop_stream()
        self.stream.close()
        self.pyaudio_instance.terminate()
        
    def pause_recording(self):
        """暂停录音"""
        self.is_paused = True
        
    def resume_recording(self):
        """恢复录音"""
        self.is_paused = False
        
    def toggle_pause(self):
        """切换暂停/恢复状态"""
        self.is_paused = not self.is_paused
        return self.is_paused
        
    def audio_callback(self, in_data, frame_count, time_info, status):
        """音频回调函数，将音频数据放入队列"""
        if not self.is_paused:
            global_audio_data_queue.put(in_data)
        return (in_data, pyaudio.paContinue)
