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
DIAL_ERROR_FILE = "dial_failures.txt"    # 拨号失败库
TRAFFIC_ERROR_FILE = "traffic_failures.txt" # 流量异常库

DEFAULT_CONFIG = {
    "target_urls": ["https://www.baidu.com"],
    "traffic_mb_goal": 2.0,
    "dial_name_prefix": "宽带连接",
    "concurrent_limit": 10
}

# --- 线程锁 (确保并发写入文件不冲突) ---
log_lock = threading.Lock()
dial_err_lock = threading.Lock()
traffic_err_lock = threading.Lock()

def write_log(message):
    with log_lock:
        timestamp = time.strftime("%H:%M:%S")
        msg = f"[{timestamp}] {message}"
        print(msg)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

def record_dial_error(user, pwd, reason):
    """专门记录拨号环节的失败"""
    with dial_err_lock:
        with open(DIAL_ERROR_FILE, "a", encoding="utf-8") as f:
            f.write(f"{user},{pwd},原因:{reason},{time.strftime('%Y-%m-%d %H:%M:%S')}\n")

def record_traffic_error(user, pwd, reason):
    """专门记录流量环节的异常"""
    with traffic_err_lock:
        with open(TRAFFIC_ERROR_FILE, "a", encoding="utf-8") as f:
            f.write(f"{user},{pwd},原因:{reason},{time.strftime('%Y-%m-%d %H:%M:%S')}\n")

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

    # 1. 断开清理
    subprocess.run(f'rasdial "{dial_name}" /disconnect', shell=True, capture_output=True)

    # 2. 拨号阶段
    write_log(f"[线程-{thread_id}] 正在拨号: {user}")
    res = subprocess.run(f'rasdial "{dial_name}" {user} {pwd}', shell=True, capture_output=True, text=True)

    if res.returncode != 0:
        error_info = res.stdout.strip() if res.stdout else res.stderr.strip()
        error_info = error_info.replace("\n", " ")
        write_log(f"[线程-{thread_id}] ❌ 拨号失败: {user}")
        # 写入拨号失败文件
        record_dial_error(user, pwd, error_info)
        return

    # 3. 流量阶段
    write_log(f"[线程-{thread_id}] ✅ 拨号成功: {user}")
    time.sleep(3) # 给系统分配IP的时间

    downloaded = 0
    target_mb = conf.get("traffic_mb_goal", 2.0)
    target_bytes = target_mb * 1024 * 1024
    success_flag = False
    fail_reason = "流量未达标"

    try:
        start_time = time.time()
        while downloaded < target_bytes:
            current_urls = load_config().get("target_urls", [])
            if not current_urls:
                fail_reason = "配置中无网址"
                break

            for url in current_urls:
                try:
                    with requests.get(url, stream=True, timeout=12, verify=False) as r:
                        r.raise_for_status()
                        for chunk in r.iter_content(chunk_size=131072):
                            if chunk:
                                downloaded += len(chunk)
                                if downloaded >= target_bytes: break
                except Exception as e:
                    write_log(f"[线程-{thread_id}] ⚠️ 网址访问失败: {url}")

                if downloaded >= target_bytes: break

            # 如果跑完一轮网址一点流量都没有，直接判定坏号
            if downloaded == 0:
                fail_reason = "网络连通但无法产生下行流量"
                break

        if downloaded >= target_bytes:
            success_flag = True
            write_log(f"[线程-{thread_id}] 🚀 流量达成: {user} ({downloaded/(1024*1024):.2f}MB)")
        else:
            fail_reason = f"流量不达标(仅完成{downloaded/(1024*1024):.2f}MB)"

    except Exception as e:
        fail_reason = f"运行异常: {str(e)}"

    # 4. 流量异常记录
    if not success_flag:
        write_log(f"[线程-{thread_id}] 🔺 记录流量异常: {user}")
        record_traffic_error(user, pwd, fail_reason)

    # 5. 断开任务
    subprocess.run(f'rasdial "{dial_name}" /disconnect', shell=True, capture_output=True)

def main():
    root = tk.Tk()
    root.withdraw()
    acc_path = filedialog.askopenfilename(title="选择宽带账号库", filetypes=[("Text", "*.txt")])
    if not acc_path: return

    with open(acc_path, "r", encoding="utf-8") as f:
        accounts = [line.strip().split(",") for line in f if "," in line]

    conf = load_config()
    concurrency = conf.get("concurrent_limit", 10)
    write_log(f"任务启动：总数 {len(accounts)}, 最大并发 {concurrency}")

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for i, (u, p) in enumerate(accounts):
            executor.submit(dial_task, u, p, (i % concurrency) + 1)
            time.sleep(1.2) # 避免 rasdial 进程冲突

    write_log("🎉 任务全部处理完毕！")
    input("按回车键结束...")

if __name__ == "__main__":
    main()