from PIL import Image # type: ignore
import time
import multiprocessing
from facial_expressions import FacialExpression
from services import wait_for_wake_word, LLM, TTS, ASR, RecordingService
import os
import threading
from dotenv import load_dotenv

load_dotenv()

# 从环境变量获取百度语音识别API配置
WS_URL = os.getenv('WS_URL')
APP_ID = os.getenv('XFYUN_APP_ID')
API_KEY = os.getenv('XFYUN_API_KEY')
API_SECRET = os.getenv('XFYUN_SECRET_KEY')

HAILUO_GROUP_ID = os.getenv('HAILUO_GROUP_ID')
HAILUO_API_KEY = os.getenv('HAILUO_API_KEY')

def display_process(display_queue):
    from gui import display

    while True:
        if not display_queue.empty():
            new_image = display_queue.get()
            if new_image == "EXIT":
                return
            display.image = new_image
        ret = display.show()
        if not ret:
            break
        time.sleep(0.01)






if __name__ == "__main__":
    print("starting the project...")
    display_queue = multiprocessing.Queue()
    display_proc = multiprocessing.Process(target=display_process, args=(display_queue,))
    display_proc.start()
    facial_expression = FacialExpression(display_queue)
    stop_event = threading.Event()
    threads = []
    try:
        facial_expression.normal()
        recording_service = RecordingService()
        tts = TTS(HAILUO_GROUP_ID, HAILUO_API_KEY)
        llm = LLM(os.getenv('DEEPSEEK_API_KEY'), os.getenv('DEEPSEEK_BASE_URL'))
        asr = ASR(WS_URL, APP_ID, API_KEY, API_SECRET)

        while True:
            continue_interaction = wait_for_wake_word()
            
            tts.say("你好，我是小爱同学，有什么可以帮你的吗？")
            recording_service.async_run()
            t1= threading.Thread(target=asr.run_forever,args=(stop_event,))
            t2= threading.Thread(target=llm.run_forever,args=(stop_event,))
            t3= threading.Thread(target=tts.run_forever,args=(stop_event,))
            t1.daemon = True
            t2.daemon = True
            t3.daemon = True
            threads = [t1, t2, t3]
            for thread in threads:
                thread.start()

            while True:
                if asr.quit_flag:
                    stop_event.set()
                    for thread in threads:
                        thread.join(timeout=2.0)
                    asr.close()
                    recording_service.close()
                    threads = []
                    stop_event.clear()

                    break
                time.sleep(0.01)
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        stop_event.set()
        
        # 等待所有线程结束
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=2.0)

        display_queue.put("EXIT")
        display_proc.join()
        print("Display process terminated")