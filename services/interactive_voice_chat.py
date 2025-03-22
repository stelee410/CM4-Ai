from dotenv import load_dotenv
import os

load_dotenv()

def voice_interaction_mode():
    print("voice interaction mode...")
    print("listening...")
    # 这里应该是实际的语音识别和处理逻辑
    # 为了演示，我们使用简单的输入
    user_input = input("Enter your command: ")
    if user_input == "q":
        return False
    print(f"Received command: {user_input}")
    return True