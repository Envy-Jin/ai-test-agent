"""
src/agent/file_api_lab.py —— File API 上传实验

Day 10 进阶：用 File API 上传图片，适合大文件或重复使用
"""

from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-3.1-flash-lite"

def upload_and_analyze(image_path: str):
    """上传图片到 File API，然后用 URI 引用"""
    print("=" * 60)
    print("🧪 File API 上传实验")
    print("=" * 60)

    # 1. 上传文件
    print(f"\n📤 上传文件：{image_path}")
    uploaded = client.files.upload(file=image_path)
    print(f"   文件名：{uploaded.name}")
    print(f"   URI：{uploaded.uri}")
    print(f"   MIME：{uploaded.mime_type}")

    # 2. 用上传后的文件调用（contents 直接传 uploaded 对象）
    print("\n🔍 用上传的文件分析...")
    response = client.models.generate_content(
        model=MODEL,
        contents=["请描述这张图片的内容", uploaded],
        config=types.GenerateContentConfig(temperature=0.2),
    )
    print(f"\nGemini 回答：{response.text}")

    # 3. 同一文件可重复使用（不用重新上传）
    print("\n🔍 同一文件第二次调用（无需重新上传）...")
    response2 = client.models.generate_content(
        model=MODEL,
        contents=["这张图里有几个按钮？只回答数字。", uploaded],
        config=types.GenerateContentConfig(temperature=0.0),
    )
    print(f"回答：{response2.text}")

    print("\n💡 File API vs 内联（PIL.Image）对比：")
    print("   内联：简单，适合小图（< 20MB），每次调用都重新传")
    print("   File API：上传一次可多次引用，适合大图或重复使用")
    print("   File API 上传的文件有有效期（通常 48 小时）")


def compare_two_images(image_path_1: str, image_path_2: str):
    """多图对比：同时传入两张图片"""
    print("\n" + "=" * 60)
    print("🧪 多图对比实验")
    print("=" * 60)

    import PIL.Image
    img1 = PIL.Image.open(image_path_1)
    img2 = PIL.Image.open(image_path_2)

    print(f"📷 图片 1：{image_path_1}")
    print(f"📷 图片 2：{image_path_2}")

    # contents 中放入多张图片
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            "请对比这两张图片，指出它们的相同点和不同点。",
            img1,
            img2,
        ],
        config=types.GenerateContentConfig(temperature=0.2),
    )
    print(f"\n对比结果：\n{response.text}")

    print("\n💡 多图对比的应用场景：")
    print("   - 设计稿 vs 实际截图对比")
    print("   - 两个版本的界面差异对比")
    print("   - 正确界面 vs 错误界面对比")


if __name__ == "__main__":
    image_path = "docs/images/mock_login.png"
    if os.path.exists(image_path):
        upload_and_analyze(image_path)
    else:
        print("⚠️  请先生成测试图片：python src/agent/make_test_image.py")

    # 多图对比（需要第二张图）
    image_path_2 = "docs/images/leetcode.png"#"docs/images/mock_login_2.png"
    if os.path.exists(image_path) and os.path.exists(image_path_2):
        compare_two_images(image_path, image_path_2)
    else:
        print("\n💡 多图对比需要两张图片。可以复制 mock_login.png 为 mock_login_2.png 来测试")

    print("\n✅ File API 实验完成！")