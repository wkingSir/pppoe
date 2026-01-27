import subprocess
import time
import requests
import os
import json
import threading
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import filedialog

# --- 配置与锁 ---
CONFIG_FILE = "config.json"
LOG_FILE = "dial_detail_log.txt"
EXCEPTION_FILE = "traffic_exceptions.txt" # 专门存放异常账号
DEFAULT_CONFIG = {
    "target_urls": ["https://www.baidu.com"],
    "traffic_mb_goal": 2.0,
    "dial_name_prefix": "宽带连接",
    "concurrent_limit": 10
}

log_lock = threading.Lock()
error_lock = threading.Lock() # 专门用于异常文件写入的锁

def write_log(message):
    with log_lock:
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")

def record_exception(user, pwd, reason):
    """将流量异常的账号和密码记录到独立文件"""
    with error_lock:
        with open(EXCEPTION_FILE, "a", encoding="utf-8") as f:
            # 格式：账号,密码,异常原因,时间
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

    # 1. 初始清理
    subprocess.run(f'rasdial "{dial_name}" /disconnect', shell=True, capture_output=True)

    # 2. 拨号
    write_log(f"[T-{thread_id}] 尝试拨号: {user}")
    res = subprocess.run(f'rasdial "{dial_name}" {user} {pwd}', shell=True, capture_output=True, text=True)

    if res.returncode != 0:
        error_msg = res.stdout.strip().replace("\n", " ")
        write_log(f"[T-{thread_id}] ❌ 拨号失败: {user} | 原因: {error_msg}")
        # 拨号失败通常不属于“流量异常”，但如果你需要，也可以记录
        return

    # 3. 流量产生逻辑
    write_log(f"[T-{thread_id}] ✅ 拨号成功: {user}")
    time.sleep(3) # 缓冲网络初始化

    downloaded = 0
    target_bytes = conf.get("traffic_mb_goal", 2.0) * 1024 * 1024
    success_flag = False
    failure_reason = "Unknown"

    try:
        start_time = time.time()
        while downloaded < target_bytes:
            # 动态获取当前配置中的网址
            current_urls = load_config().get("target_urls", [])
            if not current_urls:
                failure_reason = "No URLs in config"
                break

            for url in current_urls:
                try:
                    with requests.get(url, stream=True, timeout=12, verify=False) as r:
                        r.raise_for_status()
                        for chunk in r.iter_content(chunk_size=65536):
                            if chunk:
                                downloaded += len(chunk)
                                if downloaded >= target_bytes: break
                except Exception as e:
                    failure_reason = f"Access Error: {type(e).__name__}"
                    write_log(f"[T-{thread_id}] ⚠️ 访问异常({url}): {failure_reason}")

                if downloaded >= target_bytes: break

            # 如果循环一圈还没产生任何流量，判定为异常
            if downloaded == 0:
                break

        if downloaded >= target_bytes:
            success_flag = True
            write_log(f"[T-{thread_id}] 🚀 流量完成: {user} ({downloaded/(1024*1024):.2f}MB)")
        else:
            failure_reason = f"Traffic Incomplete ({downloaded/(1024*1024):.2f}MB)"

    except Exception as e:
        failure_reason = str(e)

    # 4. 异常处理与导出
    if not success_flag:
        write_log(f"[T-{thread_id}] 🔺 记录异常账号: {user}")
        record_exception(user, pwd, failure_reason)

    # 5. 断开连接
    subprocess.run(f'rasdial "{dial_name}" /disconnect', shell=True, capture_output=True)

def main():
    root = tk.Tk()
    root.withdraw()
    acc_path = filedialog.askopenfilename(title="请选择1000+账号文件", filetypes=[("Text", "*.txt")])
    if not acc_path: return

    with open(acc_path, "r", encoding="utf-8") as f:
        accounts = [line.strip().split(",") for line in f if "," in line]

    conf = load_config()
    write_log(f"已加载 {len(accounts)} 个账号。开始并发处理...")

    with ThreadPoolExecutor(max_workers=conf.get("concurrent_limit", 10)) as executor:
        for i, (u, p) in enumerate(accounts):
            executor.submit(dial_task, u, p, (i % 10) + 1)
            time.sleep(1.5) # 错峰拨号，防止系统 rasdial 进程锁死

if __name__ == "__main__":
    main()