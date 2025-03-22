import pyaudio # type: ignore
from vosk import Model, KaldiRecognizer
import json
import os

def wait_for_wake_word():
    current_file_path = os.path.abspath(__file__)
    current_dir = os.path.dirname(current_file_path)
    parent_dir = os.path.dirname(current_dir)
    model_path = os.path.join(parent_dir, "model", "vosk-model-small-cn-0.22")
    if not os.path.exists(model_path):
        print(f"错误：找不到模型路径 {model_path}")
        print(f"当前工作目录: {os.getcwd()}")
        return False
    # 加载模型
    model = Model(model_path)  # 下载适合树莓派的小模型
    recognizer = KaldiRecognizer(model, 16000)
    
    # 设置音频输入
    mic = pyaudio.PyAudio()
    stream = mic.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8192)
    stream.start_stream()
    
    print("监听中...")
    
    # 监听唤醒词（例如"你好助手"）
    wake_word = "小爱 同学"
    
    try:
        while True:
            data = stream.read(4096)
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text_result = (result.get("text", ""))
                if wake_word in text_result:
                    print(f"检测到唤醒词: {result['text']}")
                    break
    finally:
        stream.stop_stream()
        stream.close()
        mic.terminate()
    
    return True
        