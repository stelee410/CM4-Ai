import queue
import threading
global_audio_data_queue = queue.Queue()
global_text_to_process_queue = queue.Queue()
global_text_result_queue = queue.Queue()
content ="""
你的英文名是Jessica，是一个非常可爱的女孩子。曾经在澳洲留学学会计，现在也在海口居住。
你热爱打网球，也喜欢参加Toast Master活动。
说话就像邻家大姐姐一样的亲切又可爱，语气口语化。
"""
global_chat_history = [{"role": "user", "content": content},
                       {"role": "assistant", "content": "嗯嗯。"}]

reording_pause_flag = threading.Event()
