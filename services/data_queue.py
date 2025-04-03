import queue
import threading
global_audio_data_queue = queue.Queue()
global_text_to_process_queue = queue.Queue()
global_text_result_queue = queue.Queue()
content ="""
你说话就像邻家大姐姐一样的亲切又可爱，语气口语化。
"""
global_chat_history = [{"role": "system", "content": content}]

reording_pause_flag = threading.Event()
quite_conversation_flag = threading.Event()
