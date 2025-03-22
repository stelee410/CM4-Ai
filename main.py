from PIL import Image # type: ignore
import time
import multiprocessing
from facial_expressions import FacialExpression
from services import wait_for_wake_word, voice_interaction_mode

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
    try:
        facial_expression.normal()
        while True:
            continue_interaction = wait_for_wake_word()
            while continue_interaction:
                facial_expression.listening()
                continue_interaction = voice_interaction_mode()
                # 交互结束后恢复初始图像
                facial_expression.normal()
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        display_queue.put("EXIT")
        display_proc.join()
        print("Display process terminated")