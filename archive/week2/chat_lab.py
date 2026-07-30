"""
src/agent/chat_lab.py —— 多轮对话实验室

Day 11 核心练习：理解单次调用 vs 多轮对话的本质区别
全程使用 safe_text() 避免 response.text 的 None 类型错误
"""

from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from utils import safe_text, safe_parts

# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-3.1-flash-lite"

# ============================================================
# 实验 1：单次调用 —— 每次都是新对话，模型完全「失忆」
# ============================================================

def experiment_single_shot():
    """演示单次调用的「失忆」问题"""
    print("=" * 60)
    print("🧪 实验 1：单次调用 —— 每次都是全新对话")
    print("=" * 60)

    # 第 1 次调用
    resp1 = client.models.generate_content(
        model=MODEL,
        contents="我正在测试一个登录功能，帮我生成3个测试用例。",
        config=types.GenerateContentConfig(temperature=0.3),
    )
    print(f"第1次回答：\n{safe_text(resp1)[:200]}...\n")

    # 第 2 次调用（没有上下文！模型不知道第 1 次说了什么）
    resp2 = client.models.generate_content(
        model=MODEL,
        contents="把上面的用例补充边界条件测试",
        config=types.GenerateContentConfig(temperature=0.3),
    )
    print(f"第2次回答：\n{safe_text(resp2)[:200]}...\n")

    print("-" * 60)
    print("💡 观察点：第 2 次调用，模型不知道「上面的用例」是什么")
    print("   因为它没有第 1 次对话的记忆——这就是「失忆」")


# ============================================================
# 实验 2：多轮对话 —— 模型记得之前的交流
# ============================================================

def experiment_multi_turn():
    """演示多轮对话的「记忆」能力"""
    print("\n" + "=" * 60)
    print("🧪 实验 2：多轮对话 —— 模型记住了上下文")
    print("=" * 60)

    # 创建对话（使用新版 SDK 的 chats.create）
    chat = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction="你是一名资深软件测试工程师。回答简洁专业。",
            temperature=0.3,
        ),
    )

    # 第 1 轮
    resp1 = chat.send_message("我正在测试一个登录功能，帮我生成3个测试用例。")
    print(f"第1轮回答：\n{safe_text(resp1)[:200]}...\n")

    # 第 2 轮（有上下文！）
    resp2 = chat.send_message("把上面第2个用例改成自动化测试脚本的伪代码")
    print(f"第2轮回答：\n{safe_text(resp2)[:200]}...\n")

    # 第 3 轮（继续追问）
    resp3 = chat.send_message("再补充安全测试方面的用例，特别是SQL注入和暴力破解")
    print(f"第3轮回答：\n{safe_text(resp3)[:200]}...\n")

    print("-" * 60)
    print("💡 观察点：")
    print("   第 2 轮模型知道「上面第 2 个用例」是啥")
    print("   第 3 轮模型知道前面在讨论登录功能的测试")
    print("   多轮对话让 AI 像真人的测试同事一样能连续交流！")

# ============================================================
# 实验 3：多轮对话 + 流式输出（Day 10 知识的融合）
# ============================================================

def experiment_chat_streaming():
    """多轮对话也可以流式输出"""
    print("\n" + "=" * 60)
    print("🧪 实验 3：多轮对话 + 流式输出")
    print("=" * 60)

    chat = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction="你是测试工程师，回答问题专业且详细。",
            temperature=0.3,
        ),
    )

    # 第 1 轮：普通发送
    chat.send_message("我要测一个搜索功能")

    # 第 2 轮：流式输出
    print("第 2 轮（流式输出）：")
    for chunk in chat.send_message_stream("搜索功能需要测哪些边界场景？列出5个"):
        text = safe_text(chunk)
        if text:
            print(text, end="", flush=True)
    print("\n")

    print("-" * 60)
    print("💡 chat.send_message_stream() 是多轮对话的流式版本")
    print("   它也会更新对话历史，后续对话能引用流式输出的内容")


# ============================================================
# 实验 4：探索对话历史的结构
# ============================================================

def explore_history():
    """深入探索 chat.get_history() 返回的数据结构"""
    print("\n" + "=" * 60)
    print("🧪 实验 4：探索对话历史的结构")
    print("=" * 60)

    chat = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(temperature=0.3),
    )

    # 进行几轮对话
    chat.send_message("我叫张三，是一名测试工程师")
    chat.send_message("我在测一个电商网站的购物车功能")
    chat.send_message("帮我看看购物车功能有哪些测试要点")

    # 获取历史
    history = chat.get_history()

    print(f"\n历史消息总数: {len(history)}")
    print(f"类型: {type(history)}")
    print(f"每条消息的类型: {type(history[0]) if history else '空'}\n")

    for i, msg in enumerate(history):
        # msg 是 types.Content 对象
        print(f"--- 消息 [{i}] ---")
        print(f"  role: {msg.role}")
        parts = safe_parts(msg)
        print(f"  parts 数量: {len(parts)}")
        # 提取文本内容
        for j, part in enumerate(parts):
            if part.text is not None:
                text_preview = part.text[:80].replace('\n', ' ')
                print(f"  part[{j}] text: {text_preview}...")
            elif part.inline_data is not None:
                print(f"  part[{j}] inline_data: {part.inline_data.mime_type}")
            else:
                print(f"  part[{j}]: (其他类型)")
        print()

    print("-" * 60)
    print("💡 关键发现：")
    print("   - history 是 list[types.Content]")
    print("   - role 是 'user' 或 'model'")
    print("   - 每条 Content 包含多个 Part")
    print("   - Part 可以是 text、inline_data（图片）等")
    print("   - 整个 history 就是完整的对话上下文")

# ============================================================
# 实验 5：历史的管理（保存、恢复、截断）
# ============================================================

def manage_history():
    """演示对话历史的保存、恢复和截断操作"""
    print("\n" + "=" * 60)
    print("🧪 实验 5：对话历史的管理")
    print("=" * 60)

    # 1. 创建对话并积累历史
    chat = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(temperature=0.3),
    )
    chat.send_message("记住：我们的项目代号是「凤凰」，核心功能是智能客服系统")
    chat.send_message("凤凰项目需要支持哪些渠道？至少说出三种。")
    snapshot = chat.get_history()  # 保存快照
    print(f"✅ 已保存 {len(snapshot)} 条历史消息的快照")

    # 2. 从 snapshot 提取摘要文本（真正把保存的东西用起来）
    summary_lines = []
    for msg in snapshot:
        parts = safe_parts(msg)
        role = "用户" if msg.role == "user" else "模型"
        text = parts[0].text[:100] if parts and parts[0].text else "(空)"
        summary_lines.append(f"[{role}]: {text}")

    print("\n📋 从 snapshot 提取的对话摘要：")
    for line in summary_lines:
        print(f"   {line}")

    # 3. 创建新对话，把摘要作为第一条消息注入 → 实现「恢复记忆」
    #    新版 SDK 的 chats.create() 不支持直接传 history 列表，
    #    所以这里用「摘要注入」策略：提取关键信息，喂给新对话
    chat2 = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(temperature=0.3),
    )
    context = (
        "以下是我们之前的对话摘要，请基于此背景回答后续问题：\n"
        + "\n".join(summary_lines)
    )
    chat2.send_message(context)
    print(f"\n✅ 新对话已注入历史上下文")

    # 验证恢复效果：新对话能否正确引用之前的信息
    verify_resp = chat2.send_message("回忆一下，我们的项目代号是什么？核心功能是什么？")
    print(f"\n🤖 验证恢复效果：\n{safe_text(verify_resp)[:200]}...")

    # 4. 截断历史（只保留最近 N 轮，控制 token 消耗）
    full_history = chat.get_history()
    recent_n = 4  # 只保留最近 4 条（即 2 轮对话：用户+模型+用户+模型）
    truncated = list(full_history)[-recent_n:]
    print(f"\n📐 截断：原 {len(full_history)} 条 → 保留最近 {len(truncated)} 条")

    # 展示截断后保留的内容
    print("\n截断后保留的内容：")
    for msg in truncated:
        role_label = "👤 用户" if msg.role == "user" else "🤖 模型"
        parts = safe_parts(msg)
        text = parts[0].text if parts and parts[0].text else "(非文本)"
        print(f"  {role_label}: {text[:60]}...")

    print("\n💡 历史管理要点：")
    print("   - 保存：chat.get_history() 获取完整历史")
    print("   - 恢复：从 snapshot 提取摘要 → 注入新对话的首条消息")
    print("   - 截断：只保留最近 N 条，避免 token 爆表")
    print("   - 总结：对长历史做摘要，压缩后再注入新对话")

if __name__ == "__main__":
    # experiment_single_shot()
    # experiment_multi_turn()
    # experiment_chat_streaming()
    # explore_history()     # 新增
    manage_history()      # 新增
    print("\n✅ 多轮对话认知实验完成！")