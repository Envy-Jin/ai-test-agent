# Day 39 笔记：测试 + 文档

## 1. 改动前基线
- 裸 pytest：19 collected + 4 collection errors（逐条列根因）
- README：第 1 周版本，已过期

## 2. 今天做了什么
- V1 裸 pytest 47 passed（≈5s）；AppTest 提速 55s → 5s（module 级 fixture）
- 新增 tests/test_day39_blueprint.py(21) + tests/test_day39_cli.py(12) + conftest.py
- day35_scenario 新增 find_blueprint_contract_violations（纯函数，不改行为）
- 退休 2 个失效测试（归档）；pyproject 声明 testpaths
- README 重写 + 两张 UI 截图

## 3. 踩到的坑
- （按实际填）pyright CLI 缺 venvPath/venv → 第三方包全假错（`reportMissingImports`）→ 改配置不改代码
- （按实际填）**只看 pyright 文字会误判**：退出码 4 = 一行都没查（路径写错 / 喂了 `/c/...` 这种 Git-Bash 路径），此时它不打印 `N errors` 行
- （按实际填）monkeypatch 用字符串目标 → 同一文件两个模块对象，补丁没生效

## 4. 遗留 / 下一步（Day 40）
- register 资产补齐；执行层第 6 态 skipped_missing_input；Day 40 异步 + 缓存