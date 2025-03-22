import xgoscreen.LCD_2inch as LCD_2inch
from PIL import Image, ImageDraw, ImageFont
import time

class RealDisplay:
    def __init__(self,width=320, height=240):
        self.width = width
        self.height = height
        self.display = LCD_2inch.LCD_2inch()
        self.display.clear()
        self.image = Image.new("RGB", (width, height), (0, 0, 0))
        self.draw = ImageDraw.Draw(self.image)


    def draw_rectangle(self, rect, color):
        """绘制矩形
        rect: (x, y, w, h) - 左上角坐标和宽高
        color: (r, g, b) - RGB颜色
        """
        x, y, w, h = rect
        # ImageDraw需要两个点(左上和右下)
        self.draw.rectangle([x, y, x+w, y+h], fill=color)
    
    def draw_text(self, text, position, color=(255, 255, 255), font_scale=0.5):
        """绘制文本
        text: 要显示的文本
        position: (x, y) - 文本位置
        color: (r, g, b) - RGB颜色
        font_scale: 字体大小缩放因子
        """
        # 将OpenCV的font_scale转换为PIL的字体大小
        font_size = int(12 * font_scale * 2)  # 粗略转换
        
        try:
            # 尝试加载系统字体
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            # 如果失败，使用默认字体
            font = ImageFont.load_default()
        
        self.draw.text(position, text, fill=color, font=font)

    def load_image(self, image_path):
        self.image = Image.open(image_path)
        self.draw = ImageDraw.Draw(self.image)
    
    def show(self):
        self.display.ShowImage(self.image)
        return True
    
