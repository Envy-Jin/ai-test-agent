"""
src/agent/multimodal_lab.py —— 多模态能力实验室

Day 10 核心练习：让 Gemini「看」图片
通过截图分析实验，直观感受多模态输入的力量
"""

from google import genai
from google.genai import types
import os
import json
from dotenv import load_dotenv
import PIL.Image

# # 代理配置（按你的实际端口修改）
# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-3.1-flash-lite"

# ============================================================
# 实验 1：最简单的多模态调用 —— 让 AI 看图说话
# ============================================================

def describe_image(image_path: str):
    """让 Gemini 描述图片内容"""
    print("=" * 60)
    print("🧪 实验 1：让 Gemini 看图说话")
    print("=" * 60)

    # 加载图片
    image = PIL.Image.open(image_path)
    print(f"📷 图片：{image_path}")
    print(f"   尺寸：{image.size}，格式：{image.format}")

    # 多模态调用：contents 传入 [文本, 图片]
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            "请详细描述这张图片中的内容，包括所有可见的文字、按钮、输入框等界面元素。",
            image,
        ],
        config=types.GenerateContentConfig(temperature=0.2),
    )
    print(f"\nGemini 描述：\n{response.text}")

    print("\n" + "-" * 60)
    # print("💡 观察点：")
    # print("   - Gemini 是否识别出了图片中的所有文字？")
    # print("   - 是否理解了这是一个登录界面？")
    # print("   - 对布局的描述是否准确？")

# ============================================================
# 实验 2：方式对比 —— PIL.Image 内联 vs types.Part.from_bytes
# ============================================================

def compare_image_input_methods(image_path: str):
    """对比两种图片传入方式"""
    print("\n" + "=" * 60)
    print("🧪 实验 2：两种图片传入方式对比")
    print("=" * 60)

    # 方式 A：PIL.Image 对象（最简单，适合小图）
    print("\n--- 方式 A：PIL.Image 对象（内联） ---")
    image_a = PIL.Image.open(image_path)
    resp_a = client.models.generate_content(
        model=MODEL,
        contents=["这张图里有几个输入框？只回答数字。", image_a],
        config=types.GenerateContentConfig(temperature=0.0),
    )
    print(f"回答：{resp_a.text}")

    # 方式 B：types.Part.from_bytes（更底层，适合从 bytes 加载）
    print("\n--- 方式 B：types.Part.from_bytes ---")
    with open(image_path, "rb") as f:
        img_bytes = f.read()
    part = types.Part.from_bytes(data=img_bytes, mime_type="image/png")
    resp_b = client.models.generate_content(
        model=MODEL,
        contents=["这张图里有几个输入框？只回答数字。", part],
        config=types.GenerateContentConfig(temperature=0.0),
    )
    print(f"回答：{resp_b.text}")

    print("\n" + "-" * 60)
    # print("💡 两种方式对比：")
    # print("   方式 A（PIL.Image）：最简单，适合本地图片文件")
    # print("   方式 B（Part.from_bytes）：更灵活，适合从网络/数据库读取的图片字节")
    # print("   两种方式效果一样，按你的数据来源选择")


# ============================================================
# 实验 3：Token 消耗观察 —— 图片也占 Token
# ============================================================

def observe_image_tokens(image_path: str):
    """观察图片输入的 token 消耗"""
    print("\n" + "=" * 60)
    print("🧪 实验 3：图片输入的 Token 消耗")
    print("=" * 60)

    image = PIL.Image.open(image_path)

    # 纯文本调用的 token
    resp_text = client.models.generate_content(
        model=MODEL,
        contents="这是一个登录界面",
        config=types.GenerateContentConfig(temperature=0.2),
    )
    text_tokens = resp_text.usage_metadata.total_token_count

    # 多模态调用的 token
    resp_img = client.models.generate_content(
        model=MODEL,
        contents=["这是一个登录界面", image],
        config=types.GenerateContentConfig(temperature=0.2),
    )
    img_tokens = resp_img.usage_metadata.total_token_count

    print(f"纯文本输入 Token 数：{text_tokens}")
    print(f"图文混合输入 Token 数：{img_tokens}")
    print(f"图片额外消耗 Token：{img_tokens - text_tokens}")

    # print("\n💡 图片会按尺寸折算成 Token 消耗：")
    # print("   - 图片越大，消耗越多")
    # print("   - 建议图片宽度不超过 1536 像素")
    # print("   - 可用 image.thumbnail() 缩放后再传入")


if __name__ == "__main__":
    image_path = "docs/images/mock_login.png"
    if not os.path.exists(image_path):
        print("⚠️  请先运行 python src/agent/make_test_image.py 生成测试图片")
    else:
        # describe_image(image_path)
        # compare_image_input_methods(image_path)
        observe_image_tokens(image_path)
        print("\n✅ 多模态基础实验完成！")