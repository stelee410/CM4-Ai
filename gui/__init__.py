try:
    # 尝试导入CM4特定模块来检测环境
    import xgoscreen.LCD_2inch # type: ignore
    from .real_display import RealDisplay
    # 如果成功导入，说明是CM4环境
    display = RealDisplay(320, 240)
except ImportError:
    # 如果导入失败，使用模拟器
    from .display import DisplayEmulator
    display = DisplayEmulator(320, 240)

__all__ = ['display']