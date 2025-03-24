import queue

global_audio_data_queue = queue.Queue()
global_text_to_process_queue = queue.Queue()
global_text_result_queue = queue.Queue()

global_chat_history = []
