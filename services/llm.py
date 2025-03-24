from openai import OpenAI
from services.data_queue import global_text_to_process_queue, global_text_result_queue,global_chat_history
import time
class LLM:
    def __init__(self, api_key, base_url):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
    def multi_circle_chat(self, text):
        user_message = {"role": "user", "content": text}
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=global_chat_history + [user_message]
        )
        global_chat_history.append(user_message)
        global_chat_history.append({"role": "assistant", "content": response.choices[0].message.content})
        return response.choices[0].message.content
    def get_response(self, text):
        messages = [{"role": "user", "content": text}]
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages
        )
        return response.choices[0].message.content

    def run_forever(self, stop_event):
        while not stop_event.is_set():
            if global_text_to_process_queue.empty():
                continue
            text = global_text_to_process_queue.get()
            response = self.multi_circle_chat(text)
            global_text_result_queue.put(response)
            time.sleep(0.01)
