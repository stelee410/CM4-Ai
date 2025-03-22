import os
from PIL import Image # type: ignore
import time
import threading

class FacialExpression:
    def __init__(self, display_queue, width=320, height=240):
        self.root_pic_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pics")
        self.width = width
        self.height = height
        self.display_queue = display_queue
        self.animation_thread = None
        self.stop_animation = False
    
    def __generate_pic_w_background(self, eyes_image, bg_color=(0, 0, 0)):
        output_image = Image.new("RGB", (self.width, self.height), bg_color)
        EYE_SCALE_FACTOR = 0.4
        eyes_scaled = eyes_image.resize((int(eyes_image.width * EYE_SCALE_FACTOR), int(eyes_image.height * EYE_SCALE_FACTOR)), Image.LANCZOS)
        eyes_x = (self.width - eyes_scaled.width) // 2
        eyes_y = self.height // 10 
        output_image.paste(eyes_scaled, (eyes_x, eyes_y), eyes_scaled)
        return output_image
    
    def normal(self):
        # 停止任何正在运行的动画
        self.stop_animation = True
        if self.animation_thread and self.animation_thread.is_alive():
            self.animation_thread.join()
        
        # 显示正常状态
        eyes_image = Image.open(os.path.join(self.root_pic_dir, "normal.png"))
        display_image = self.__generate_pic_w_background(eyes_image)
        self.display_queue.put(display_image)
        
    def listening(self):
        # 停止任何正在运行的动画
        self.stop_animation = True
        if self.animation_thread and self.animation_thread.is_alive():
            self.animation_thread.join()
        
        # 重置停止标志
        self.stop_animation = False
        
        # 启动新的动画线程
        self.animation_thread = threading.Thread(target=self.__listening_animation)
        self.animation_thread.daemon = True
        self.animation_thread.start()
    
    def __listening_animation(self):
        eyes_image = Image.open(os.path.join(self.root_pic_dir, "normal.png"))
        
        # 定义背景颜色变化
        purple = (128, 0, 128)  # 紫色
        black = (0, 0, 0)       # 黑色
        
        while not self.stop_animation:
            # 从黑色渐变到紫色
            for i in range(10):
                if self.stop_animation:
                    return
                    
                # 计算当前颜色
                r = int(black[0] + (purple[0] - black[0]) * i / 10)
                g = int(black[1] + (purple[1] - black[1]) * i / 10)
                b = int(black[2] + (purple[2] - black[2]) * i / 10)
                current_color = (r, g, b)
                
                # 生成并显示图像
                display_image = self.__generate_pic_w_background(eyes_image, current_color)
                self.display_queue.put(display_image)
                time.sleep(0.05)
            
            # 保持紫色一段时间
            if not self.stop_animation:
                time.sleep(0.5)
            
            # 从紫色渐变回黑色
            for i in range(10):
                if self.stop_animation:
                    return
                    
                # 计算当前颜色
                r = int(purple[0] + (black[0] - purple[0]) * i / 10)
                g = int(purple[1] + (black[1] - purple[1]) * i / 10)
                b = int(purple[2] + (black[2] - purple[2]) * i / 10)
                current_color = (r, g, b)
                
                # 生成并显示图像
                display_image = self.__generate_pic_w_background(eyes_image, current_color)
                self.display_queue.put(display_image)
                time.sleep(0.05)
            
            # 保持黑色一段时间
            if not self.stop_animation:
                time.sleep(0.5)

