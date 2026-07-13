# tests/test_basic.py —— pytest 入门练习

def test_addition():
    """最简单的测试：验证加法"""
    assert 1 + 1 == 2

def test_string_concat():
    """验证字符串拼接"""
    assert "hello" + " world" == "hello world"

def test_list_length():
    """验证列表长度"""
    items = [1, 2, 3]
    assert len(items) == 3

def test_dict_key():
    """验证字典键存在"""
    data = {"name": "test", "priority": "P1"}
    assert "name" in data
    assert data["priority"] == "P1"

# 更多断言模式

def test_assert_true_false():
    """布尔值断言"""
    assert True
    assert not False

def test_assert_in():
    """包含断言"""
    text = "密码不少于8位且必须包含数字"
    assert "不少于" in text
    assert "必须" in text
    assert "禁止" not in text   # 不包含

def test_assert_almost_equal():
    """近似相等断言（浮点数比较）"""
    result = 1 / 3
    # pytest 用 abs(a-b) < tolerance
    assert abs(result - 0.333) < 0.01

def test_assert_exception():
    """异常断言：验证代码确实会抛出指定异常"""
    import pytest

    # 验证除零会抛 ZeroDivisionError
    with pytest.raises(ZeroDivisionError):
      1 / 0

    # 验证访问不存在 key 会抛 KeyError
    with pytest.raises(KeyError):
      {"name": "test"}["missing_key"]

def test_assert_none():
    """None 断言"""
    result = None
    assert result is None

    found = {"id": "TC-001"}
    assert found is not None