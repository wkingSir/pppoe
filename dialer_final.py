import subprocess
import time
import requests
import os
import json
import threading
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import filedialog

# --- 核心配置 ---
CONFIG_FILE = "config.json"
LOG_FILE = "dial_detail_log.txt"
EXCEPTION_FILE = "traffic_exceptions.txt" # 统一异常账号库
DEFAULT_CONFIG = {
    "target_urls": ["https://www.baidu.com"],
    "traffic_mb_goal": 2.0,
    "dial_name_prefix": "宽带连接",
    "concurrent_limit": 10
}

# --- 线程锁 ---
log_lock = threading.Lock()
error_lock = threading.Lock()

def write_log(message):
    with log_lock:
        timestamp = time.strftime("%H:%M:%S")
        msg = f"[{timestamp}] {message}"
        print(msg)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

def record_exception(user, pwd, reason):
    """记录所有异常情况：包括拨号失败和流量不达标"""
    with error_lock:
        with open(EXCEPTION_FILE, "a", encoding="utf-8") as f:
            # 格式：账号,密码,错误原因,时间
            f.write(f"{user},{pwd},{reason},{time.strftime('%Y-%m-%d %H:%M:%S')}\n")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return DEFAULT_CONFIG

def dial_task(user, pwd, thread_id):
    conf = load_config()
    dial_name = conf.get("dial_name_prefix", "宽带连接")

    # 1. 断开上次残留连接
    subprocess.run(f'rasdial "{dial_name}" /disconnect', shell=True, capture_output=True)

    # 2. 执行拨号
    write_log(f"[T-{thread_id}] 正在拨号: {user}")
    # capture_output=True 捕获 Windows 报错信息
    res = subprocess.run(f'rasdial "{dial_name}" {user} {pwd}', shell=True, capture_output=True, text=True)

    if res.returncode != 0:
        # 提取具体的错误信息（如错误 691 等）
        error_info = res.stdout.strip() if res.stdout else res.stderr.strip()
        error_info = error_info.replace("\n", " ")
        write_log(f"[T-{thread_id}] ❌ 拨号失败: {user} | 原因: {error_info}")
        # 【新增】记录拨号失败到异常文件
        record_exception(user, pwd, f"拨号失败: {error_info}")
        return

    # 3. 拨号成功，开始跑流量
    write_log(f"[T-{thread_id}] ✅ 拨号成功: {user}")
    time.sleep(3) # 网络预热

    downloaded = 0
    target_mb = conf.get("traffic_mb_goal", 2.0)
    target_bytes = target_mb * 1024 * 1024
    success_flag = False
    fail_reason = "流量未达标"

    try:
        while downloaded < target_bytes:
            current_urls = load_config().get("target_urls", [])
            if not current_urls:
                fail_reason = "配置中无网址"
                break

            for url in current_urls:
                try:
                    # 使用 stream=True 确保真实下行流量产生
                    with requests.get(url, stream=True, timeout=12, verify=False) as r:
                        r.raise_for_status()
                        for chunk in r.iter_content(chunk_size=131072): # 128KB 块提高效率
                            if chunk:
                                downloaded += len(chunk)
                                if downloaded >= target_bytes: break
                except Exception as e:
                    write_log(f"[T-{thread_id}] ⚠️ 访问网址异常: {url} | {type(e).__name__}")

                if downloaded >= target_bytes: break

            # 如果一轮下来完全没流量，直接终止
            if downloaded == 0:
                fail_reason = "无法产生流量(所有网址失效)"
                break

        if downloaded >= target_bytes:
            success_flag = True
            write_log(f"[T-{thread_id}] 🚀 流量达标: {user} ({downloaded/(1024*1024):.2f}MB)")
        else:
            fail_reason = f"流量不达标(仅完成{downloaded/(1024*1024):.2f}MB)"

    except Exception as e:
        fail_reason = f"程序运行时异常: {str(e)}"

    # 4. 流量异常记录
    if not success_flag:
        write_log(f"[T-{thread_id}] 🔺 记录流量异常账号: {user}")
        record_exception(user, pwd, fail_reason)

    # 5. 任务结束断开
    subprocess.run(f'rasdial "{dial_name}" /disconnect', shell=True, capture_output=True)

def main():
    # 初始化 GUI 选择文件
    root = tk.Tk()
    root.withdraw()
    acc_path = filedialog.askopenfilename(title="选择宽带账号文件", filetypes=[("Text", "*.txt")])
    if not acc_path: return

    # 加载账号
    with open(acc_path, "r", encoding="utf-8") as f:
        accounts = [line.strip().split(",") for line in f if "," in line]

    conf = load_config()
    concurrency = conf.get("concurrent_limit", 10)
    write_log(f"启动！总账号:{len(accounts)} | 并发数:{concurrency}")

    # 线程池执行任务
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for i, (u, p) in enumerate(accounts):
            executor.submit(dial_task, u, p, (i % concurrency) + 1)
            # 关键：稍微错开启动时间，防止 Windows 拨号组件（rasdial）发生死锁
            time.sleep(1.2)

    write_log("🎉 所有任务已处理完成！")
    input("按回车键退出程序...")

if __name__ == "__main__":
    main()