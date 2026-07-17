"""测试脚本 - 模拟前端调用多智能体竞品调研系统

使用方法:
1. 先启动服务: python run.py
2. 再运行本脚本: python tests/test_research.py

本脚本模拟前端的完整调用流程:
1. 健康检查
2. 提交调研任务
3. 轮询任务状态
4. 打印最终报告和各阶段中间结果
"""

import time
import httpx

BASE_URL = "http://127.0.0.1:8000"


def print_separator(title: str = ""):
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
    print("=" * 60)


def test_health():
    """测试1: 健康检查"""
    print_separator("测试1: 健康检查")
    response = httpx.get(f"{BASE_URL}/api/v1/health", timeout=10)
    data = response.json()
    print(f"状态: {data['status']}")
    print(f"服务: {data['service']}")
    assert data["status"] == "ok", "健康检查失败"
    print("✓ 健康检查通过")


def test_research():
    """测试2: 完整调研流程"""
    print_separator("测试2: 提交调研任务")

    # 构造请求
    request_data = {
        "topic": "调研国内AI大模型竞品市场格局",
        "competitors": ["文心一言", "通义千问", "豆包", "Kimi", "DeepSeek"],
        "focus_dimensions": ["产品功能", "定价策略", "技术路线", "用户规模", "市场表现"],
    }

    print(f"调研主题: {request_data['topic']}")
    print(f"竞品列表: {', '.join(request_data['competitors'])}")
    print(f"关注维度: {', '.join(request_data['focus_dimensions'])}")

    # 提交任务
    response = httpx.post(
        f"{BASE_URL}/api/v1/research",
        json=request_data,
        timeout=30,
    )
    data = response.json()
    task_id = data["task_id"]
    print(f"\n任务已创建, task_id: {task_id}")
    print(f"初始状态: {data['status']}")

    # 轮询任务状态
    print_separator("轮询任务状态")
    max_wait = 600  # 最多等待10分钟
    poll_interval = 5  # 每5秒轮询一次
    elapsed = 0

    while elapsed < max_wait:
        response = httpx.get(
            f"{BASE_URL}/api/v1/research/{task_id}",
            timeout=10,
        )
        data = response.json()
        status = data["status"]

        print(f"[{elapsed}s] 状态: {status}", end="")

        if status == "running":
            print(" (多Agent协作执行中...)")
        elif status == "completed":
            print(" ✓ 完成!")
            break
        elif status == "failed":
            print(f" ✗ 失败: {data.get('error', '未知错误')}")
            break
        else:
            print(" (等待中...)")

        time.sleep(poll_interval)
        elapsed += poll_interval

    if status != "completed":
        print(f"\n任务未能在 {max_wait}s 内完成")
        return

    # 打印各阶段中间结果
    print_separator("各阶段执行结果")
    for stage in data.get("stages", []):
        print(f"\n--- {stage['stage']} [{stage['status']}] ---")
        summary = stage.get("summary", "")
        # 截取前300字展示
        if len(summary) > 300:
            print(summary[:300] + "\n... (已截断)")
        else:
            print(summary or "(无)")

    # 打印最终报告
    print_separator("最终调研报告")
    report = data.get("final_report", "")
    if report:
        print(report)
    else:
        print("(未生成报告)")

    print_separator("测试完成")
    print(f"任务ID: {task_id}")
    print(f"报告长度: {len(report)} 字")


def test_invalid_task():
    """测试3: 查询不存在的任务"""
    print_separator("测试3: 查询不存在的任务")
    response = httpx.get(f"{BASE_URL}/api/v1/research/nonexistent", timeout=10)
    print(f"状态码: {response.status_code}")
    assert response.status_code == 404, "应该返回404"
    print("✓ 正确返回404")


if __name__ == "__main__":
    print("\n" + "🔬 多智能体竞品调研系统 - 测试脚本")
    print("=" * 60)

    try:
        # 先检查服务是否可用
        try:
            test_health()
        except httpx.ConnectError:
            print("\n❌ 无法连接到服务，请先启动: python run.py")
            exit(1)

        # 运行完整调研测试
        test_research()

        # 运行异常测试
        test_invalid_task()

        print("\n✅ 所有测试通过!")

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        raise
