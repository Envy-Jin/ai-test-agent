"""
src/agent/make_test_image.py —— 生成一张测试用的模拟 UI 截图

没有真实截图时，用 Pillow 画一个简单的登录界面用于测试多模态能力
"""
from PIL import Image, ImageDraw, ImageFont
import os


def make_login_screenshot(output_path: str = "docs/images/mock_login.png") -> str:
    """生成一张模拟登录页面的截图"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 创建画布（手机屏幕比例 9:16）
    width, height = 360, 640
    img = Image.new("RGB", (width, height), color="#F5F5F5")
    draw = ImageDraw.Draw(img)

    # 尝试加载支持中文的字体（跨平台兼容）
    def _load_font(size: int):
        """按优先级查找系统中文字体，失败则回退到默认字体"""
        candidates = [
            # Windows 常见中文字体
            r"C:\Windows\Fonts\msyh.ttc",          # 微软雅黑
            r"C:\Windows\Fonts\msyhbd.ttc",        # 微软雅黑 Bold
            r"C:\Windows\Fonts\simhei.ttf",        # 黑体
            r"C:\Windows\Fonts\simsun.ttc",        # 宋体
            # macOS 常见中文字体
            "/System/Library/Fonts/PingFang.ttc",   # 苹方
            "/Library/Fonts/Arial Unicode.ttf",
            # Linux 常见中文字体
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            # 最后尝试 arial（不支持中文，但能保证英文正常）
            "arial.ttf",
        ]
        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except (IOError, OSError):
                continue
        return ImageFont.load_default()

    font_title = _load_font(28)
    font_label = _load_font(14)
    font_small = _load_font(12)

    # 标题栏
    draw.rectangle([0, 0, width, 56], fill="#4A90D9")
    draw.text((120, 16), "用户登录", fill="white", font=font_title)

    # Logo 区域
    draw.rectangle([120, 90, 240, 150], fill="#4A90D9")
    draw.text((150, 110), "LOGO", fill="white", font=font_label)

    # 手机号输入框
    draw.text((30, 180), "手机号", fill="#333333", font=font_label)
    draw.rectangle([30, 200, 330, 240], outline="#CCCCCC", width=1)
    draw.text((40, 212), "请输入手机号", fill="#999999", font=font_small)

    # 验证码输入框 + 获取按钮
    draw.text((30, 260), "验证码", fill="#333333", font=font_label)
    draw.rectangle([30, 280, 230, 320], outline="#CCCCCC", width=1)
    draw.text((40, 292), "请输入验证码", fill="#999999", font=font_small)
    draw.rectangle([240, 280, 330, 320], fill="#4A90D9")
    draw.text((255, 292), "获取验证码", fill="white", font=font_small)

    # 密码输入框
    draw.text((30, 340), "密码", fill="#333333", font=font_label)
    draw.rectangle([30, 360, 330, 400], outline="#CCCCCC", width=1)
    draw.text((40, 372), "请输入密码", fill="#999999", font=font_small)

    # 登录按钮
    draw.rectangle([30, 430, 330, 480], fill="#4A90D9")
    draw.text((150, 445), "登 录", fill="white", font=font_title)

    # 底部链接
    draw.text((90, 510), "忘记密码？", fill="#4A90D9", font=font_small)
    draw.text((200, 510), "立即注册", fill="#4A90D9", font=font_small)

    # 底部协议
    draw.text((60, 580), "登录即同意《用户协议》和《隐私政策》", fill="#999999", font=font_small)

    img.save(output_path)
    print(f"✅ 测试截图已生成：{output_path}")
    print(f"   尺寸：{width}x{height}")
    return output_path


if __name__ == "__main__":
    make_login_screenshot()
