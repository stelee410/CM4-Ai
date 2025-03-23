import os
import time
import threading
import queue
import pyaudio
import wave
import numpy as np
import json
import websocket
import base64
from urllib.parse import urlencode
import hmac
import hashlib
import datetime

from urllib.parse import urlparse, urlencode




# 设置音频参数
RATE = 16000
SILENCE_DURATION = 2.0  # 设置语音识别的阈值
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1

class InteractiveVoiceChat:
    def __init__(self,hosturl, app_id, api_key, api_secret):
        self.audio_queue = queue.Queue()
        self.text_buffer = ""
        self.current_text = ""
        self.is_model_processing = False
        self.should_interrupt = False
        self.ws = None
        self.last_speech_time = 0
        self.is_speaking = False
        self.hosturl = hosturl
        self.api_key = api_key
        self.api_secret = api_secret
        self.app_id = app_id
        self.ws_might_be_connected = False
        self.response=""

    def __hmac_with_sha_to_base64(self, string_to_sign, secret):
        key = secret.encode('utf-8')
        message = string_to_sign.encode('utf-8')
        digester = hmac.new(key, message, hashlib.sha256)
        signature = base64.b64encode(digester.digest()).decode('utf-8')
        return signature

    def assemble_auth_url(self):
        ul = urlparse(self.hosturl)
        
        # 签名时间
        date = time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())
    
        # 参与签名的字段 host, date, request-line
        sign_string = ["host: " + ul.netloc, "date: " + date, "GET " + ul.path + " HTTP/1.1"]
    
        # 拼接签名字符串
        sign = "\n".join(sign_string)
    
        # 签名结果
        sha = self.__hmac_with_sha_to_base64(sign, self.api_secret)
    
        # 构建请求参数 此时不需要urlencoding
        auth_url = 'api_key="{}", algorithm="{}", headers="{}", signature="{}"'.format(
            self.api_key, "hmac-sha256", "host date request-line", sha)
    
        # 将请求参数使用base64编码
        authorization = base64.b64encode(auth_url.encode('utf-8')).decode('utf-8')
    
        # 构建URL参数
        v = {
            "host": ul.netloc,
            "date": date,
            "authorization": authorization
        }
        
        # 将编码后的字符串url encode后添加到url后面
        call_url = self.hosturl + "?" + urlencode(v)
        return call_url
    
    def on_message(self, ws,message):
        print(f"收到消息: {message}")
        try:
            result = json.loads(message)
            if result["code"] == 0:
                data = result["data"]["result"]["ws"]
                text = ""
                for i in data:
                    for w in i["cw"]:
                        text += w["w"]
                print(f"识别结果: {text}")
                self.current_text = text
                self.is_speaking = True
                self.last_speech_time = time.time()
                # 检查是否需要发送给大模型处理
                self.check_and_process_text()
            else:
                print(f"错误: {result['message']}")
        except Exception as e:
            print(f"处理消息时出错: {e}")


    def on_error(self,ws, error):
        """WebSocket错误回调"""
        print(f"WebSocket错误: {error}")

    def on_close(self,ws, close_status_code, close_msg):
        """WebSocket关闭回调"""
        print(f"WebSocket连接关闭: {close_status_code} - {close_msg}")
        if close_status_code == 1000: #timeout
            self.ws_might_be_connected = False
        pass

    def on_open(self,ws):
        """WebSocket打开回调"""
        print("WebSocket连接已建立，开始发送音频数据...")
        def send_audio():
            """发送音频数据到WebSocket"""
            # 发送开始参数
            start_params = json.dumps({
                "common": {
                    "app_id": self.app_id
                },
                "business": {
                    "language": "zh_cn",
                    "domain": "iat",
                    "accent": "mandarin",
                    "vad_eos": 3000,
                    "dwa": "wpgs"  # 开启动态修正功能
                },
                "data": {
                    "status": 0,
                    "format": "audio/L16;rate=16000",
                    "encoding": "raw",
                    "audio": ""
                }
            })
            ws.send(start_params)
            
            # 音频状态，0:第一帧，1:中间帧，2:最后一帧
            status = 1
            
            while ws.sock and ws.sock.connected:
                try:
                    if self.audio_queue.empty():
                        time.sleep(0.1)
                        continue
                    audio_data = self.audio_queue.get()
                    self.check_silence(audio_data)
                    if self.is_speaking:
                        print("说话中...",end="\r", flush=True)
                        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                    
                        # 发送音频数据
                        audio_params = json.dumps({
                            "data": {
                                "status": status,
                                "format": "audio/L16;rate=16000",
                                "encoding": "raw",
                                "audio": audio_base64
                            }
                        })
                        ws.send(audio_params)
                    else:
                        print("静默中...",end="\r", flush=True)

                    time.sleep(0.1)
                except Exception as e:
                    print(f"发送音频数据时出错: {e}")
                    break
            
            # 发送结束参数
            try:
                if ws.sock and ws.sock.connected:
                    end_params = json.dumps({
                        "data": {
                            "status": 2  # 最后一帧音频
                        }
                    })
                    ws.send(end_params)
            except Exception as e:
                print(f"发送结束参数时出错: {e}")
        
            # 启动发送音频数据的线程
        threading.Thread(target=send_audio).start()

    def check_silence(self,audio_data):   
        # 将字节数据转换为数值数组
        data = np.frombuffer(audio_data, dtype=np.int16)
        # 计算音量
        volume = np.abs(data).mean()
    
        # 如果音量低于阈值，可能是静音
        if volume < 500:  # 阈值可以根据实际情况调整
            # 如果之前检测到语音，现在可能是停顿
            if self.is_speaking and (time.time() - self.last_speech_time > SILENCE_DURATION):
                self.is_speaking = False
                self.check_and_process_text()
        else:
            # 检测到语音
            self.is_speaking = True
            self.last_speech_time = time.time()


    def check_and_process_text(self):
        if not self.current_text:
            return
        
        # 将当前识别文本添加到缓冲区
        self.text_buffer += " " + self.current_text
    
        print(f"\n准备处理文本: {self.text_buffer}")
        self.current_text = ""  # 清空当前文本
        
        # 检查是否需要中断当前处理
        if self.is_model_processing:
            self.should_interrupt = True
            print("检测到新语音输入，将中断当前处理")
        else:
            # 启动大模型处理线程
            threading.Thread(target=self.process_with_model, args=(self.text_buffer,)).start()

    def process_with_model(self,text):
        
        self.is_model_processing = True
        print(f"大模型开始处理: {text}")
        if text == "退出" or text == "结束":
            self.response = "EXIT"
            self.is_model_processing = False
            self.should_interrupt = False
            return
        
        # 模拟大模型处理时间
        for i in range(3):  # 模拟10秒处理时间
            if self.should_interrupt:
                print("检测到新语音输入，中断当前处理")
                self.is_model_processing = False
                self.should_interrupt = False
                return
            time.sleep(1)
        
        # 模拟大模型响应
        model_response = f"大模型回复: 已处理'{text}"
        print(model_response)
        
        # 处理完成，清空文本缓冲区
        self.text_buffer = ""
        self.is_model_processing = False
        self.should_interrupt = False
        self.response = model_response
    def audio_callback(self,in_data, frame_count, time_info, status):
        """音频回调函数，将音频数据放入队列"""
        self.audio_queue.put(in_data)
        return (in_data, pyaudio.paContinue)

    def run(self):
        
        print("语音交互模式已启动...")
    
        # 检查API密钥是否已设置
        if not all([self.app_id, self.api_key, self.api_secret]):
            print("错误：讯飞语音API密钥未设置。请检查.env文件。")
            return False
    
        # 初始化PyAudio
        p = pyaudio.PyAudio()
    
        # 打开音频流
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
            stream_callback=self.audio_callback
        )
    
        # 启动WebSocket连接
        websocket.enableTrace(False)
        ws_url = self.assemble_auth_url()
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        self.ws_might_be_connected = True
        
        # 启动WebSocket线程
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
    
        # 开始录音
        stream.start_stream()
        continue_interaction = True
    
        try:
            print("请开始说话，系统会实时识别...")
            print("说'退出'或'结束'可以退出程序")
            
            # 主循环
            while True:
                time.sleep(0.1)  # 减少CPU使用率
                
                # 检查是否要退出
                if "EXIT" in self.response:
                    print("检测到退出命令，正在退出...")
                    continue_interaction =  False
                    break
                if not self.ws_might_be_connected:
                    continue_interaction = True
                    break
        
        except KeyboardInterrupt:
            print("用户中断，正在退出...")
            continue_interaction = False
        finally:
            # 清理资源
            if ws:
                ws.close()
            stream.stop_stream()
            stream.close()
            p.terminate()
            print("语音交互模式已退出")

        return continue_interaction
        
        