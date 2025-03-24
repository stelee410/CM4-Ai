import hmac
import hashlib
import base64
import time
from urllib.parse import urlparse, urlencode
import pyaudio
import websocket
import threading
import time
import queue
import json
from services.data_queue import global_text_to_process_queue
from services.data_queue import global_audio_data_queue
import numpy as np
import time
RATE = 16000
SILENCE_DURATION = 1.0  # 缩短静默阈值，使反应更快速
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
TEXT_END_MARK = "|"
TEXT_STOP_SIGN = "退出"

def hmac_with_sha_to_base64(string_to_sign, secret):
        key = secret.encode('utf-8')
        message = string_to_sign.encode('utf-8')
        digester = hmac.new(key, message, hashlib.sha256)
        signature = base64.b64encode(digester.digest()).decode('utf-8')
        return signature

def assemble_auth_url(hosturl, api_key, api_secret):
    ul = urlparse(hosturl)
        
    # 签名时间
    date = time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())
    
    # 参与签名的字段 host, date, request-line
    sign_string = ["host: " + ul.netloc, "date: " + date, "GET " + ul.path + " HTTP/1.1"]
    
    # 拼接签名字符串
    sign = "\n".join(sign_string)
    
    # 签名结果
    sha = hmac_with_sha_to_base64(sign, api_secret)
    
    # 构建请求参数 此时不需要urlencoding
    auth_url = 'api_key="{}", algorithm="{}", headers="{}", signature="{}"'.format(
            api_key, "hmac-sha256", "host date request-line", sha)
    
    # 将请求参数使用base64编码
    authorization = base64.b64encode(auth_url.encode('utf-8')).decode('utf-8')
    
        # 构建URL参数
    v = {
            "host": ul.netloc,
            "date": date,
            "authorization": authorization
        }
        
    # 将编码后的字符串url encode后添加到url后面
    call_url = hosturl + "?" + urlencode(v)
    return call_url

class ASR:
    
    def __init__(self, hosturl, app_id, api_key, api_secret):
        self.hosturl = hosturl
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.text_buffer = ""
        self.current_text = ""
        self.is_speaking = True
        self.last_speech_time = 0
        self.ws = None
        self.quit_flag = False
        # 优化音频缓冲区大小，减少累积时间以降低延迟
        self.audio_buffer = []
        self.buffer_max_size = int(RATE * 1 / CHUNK)  # 减少到约1秒的数据
        # 添加音量历史记录，用于更稳定的判断
        self.volume_history = []
        self.volume_history_max = 5  # 保存最近5次音量值

    def run(self):

        websocket.enableTrace(False)
        ws_url = assemble_auth_url(self.hosturl, self.api_key, self.api_secret)
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        self.ws = ws
        ws.run_forever()
    def run_forever(self, stop_event):
        while not stop_event.is_set():
            self.run()
            time.sleep(0.01)

    def is_connected(self):
        return self.ws and self.ws.sock and self.ws.sock.connected
    def close(self):
        self.ws.close()

    def submit(self):
        if self.text_buffer != "":    
            global_text_to_process_queue.put(self.text_buffer)
        self.text_buffer = ""
        self.current_text = ""

    def on_message(self, ws, message):
        if self.quit_flag:
            return
        try:
            result = json.loads(message)
            if result["code"] == 0:
                data = result["data"]["result"]["ws"]
                text = ""
                for i in data:
                    for w in i["cw"]:
                        text += w["w"]
                if text == TEXT_STOP_SIGN:
                    self.quit_flag = True
                    return
                self.current_text = text
                self.is_speaking = True
                self.last_speech_time = time.time()
                # 检查是否需要发送给大模型处理
                self.check_and_process_text()
            else:
                print(f"错误: {result['message']}")
        except Exception as e:
            print(f"处理消息时出错: {e}")
    def check_and_process_text(self):
        if not self.current_text:
            return
        elif self.current_text == TEXT_END_MARK:
            self.submit()
        else:
            self.text_buffer += " " + self.current_text
        self.current_text = ""
    def on_error(self,ws, error):
        """WebSocket错误回调"""
        print(f"WebSocket错误: {error}")

    def on_close(self,ws, close_status_code, close_msg):
        """WebSocket关闭回调"""
        print(f"WebSocket连接关闭: {close_status_code} - {close_msg}")
        if close_status_code == 1000: #timeout
            self.submit()
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
                    "vad_eos": 2000,  # 降低VAD超时，加快识别结束
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
            
            # 是否刚从静默状态转换为说话状态的标志
            just_spoke = False
            
            while ws.sock and ws.sock.connected:
                try:
                    if global_audio_data_queue.empty():
                        time.sleep(0.05)  # 减少等待时间以降低延迟
                        continue
                    audio_data = global_audio_data_queue.get()
                    
                    # 快速处理音频数据，获取当前状态
                    current_state = self.check_silence(audio_data)
                    
                    # 如果刚从静默转为说话，需要结束上一个会话并开始新会话
                    if not self.is_speaking and current_state:
                        self.is_speaking = True
                        just_spoke = True
                        # 清空文本缓冲区，准备新的识别
                        self.submit()
                    elif self.is_speaking and not current_state:
                        # 从说话转为静默
                        self.is_speaking = False
                        print("静默中...", end="\r", flush=True)
                        self.current_text = TEXT_END_MARK
                        # 准备新会话
                        ws.send(start_params)
                    
                    # 正在说话状态下，发送音频数据
                    if self.is_speaking:
                        print("说话中...", end="\r", flush=True)
                        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                        
                        # 发送音频数据
                        audio_params = json.dumps({
                            "data": {
                                "status": 1,  # 始终使用中间帧状态
                                "format": "audio/L16;rate=16000",
                                "encoding": "raw",
                                "audio": audio_base64
                            }
                        })
                        ws.send(audio_params)
                        just_spoke = False
                    
                    time.sleep(0.02)  # 减少循环间隔，提高响应速度
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
                    self.submit()
            except Exception as e:
                print(f"发送结束参数时出错: {e}")
        
        # 启动发送音频数据的线程
        threading.Thread(target=send_audio).start()

    def check_silence(self, audio_data):   
        """检测音频是否为静默，并返回当前检测到的状态（有声音True/静默False）"""
        # 快速计算当前音频片段的音量
        current_data = np.frombuffer(audio_data, dtype=np.int16)
        current_volume = np.abs(current_data).mean()
        
        # 将当前音频数据添加到缓冲区
        self.audio_buffer.append(current_data)
        
        # 保持缓冲区大小不超过设定的最大值
        if len(self.audio_buffer) > self.buffer_max_size:
            self.audio_buffer.pop(0)
        
        # 将当前音量添加到历史记录
        self.volume_history.append(current_volume)
        if len(self.volume_history) > self.volume_history_max:
            self.volume_history.pop(0)
        
        # 计算平均音量和当前音量
        avg_volume = sum(self.volume_history) / len(self.volume_history)
        
        # 计算缓冲区的累积音量（用于更稳定的判断）
        if len(self.audio_buffer) > 2:
            combined_data = np.concatenate(self.audio_buffer)
            buffer_volume = np.abs(combined_data).mean()
        else:
            buffer_volume = current_volume
        
        # 动态音量阈值，使用平均值的0.8倍作为基准
        threshold = 300  # 基础阈值
        dynamic_threshold = max(threshold, avg_volume * 0.8)
        
        # 打印调试信息（仅在控制台显示）
        print(f"当前音量: {current_volume:.1f}, 平均: {avg_volume:.1f}, 缓冲: {buffer_volume:.1f}, 阈值: {dynamic_threshold:.1f}", end="\r", flush=True)
        
        # 使用组合条件进行判断，使状态变化更灵敏
        is_speaking_now = False
        
        # 如果当前音量明显高于阈值，立即认为是说话状态
        if current_volume > dynamic_threshold * 1.2:
            is_speaking_now = True
            self.last_speech_time = time.time()
        # 如果缓冲区音量高于阈值，也认为是说话状态
        elif buffer_volume > dynamic_threshold:
            is_speaking_now = True
            self.last_speech_time = time.time()
        # 如果当前为说话状态，且静默时间不够长，保持说话状态
        elif time.time() - self.last_speech_time < SILENCE_DURATION:
            is_speaking_now = True
        
        return is_speaking_now

        
            
