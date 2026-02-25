import subprocess
import time
import requests
import os
import shutil
import tkinter as tk
from tkinter import filedialog, simpledialog

# --- 核心配置 ---
ADSL_NAME = "宽带连接"
TRAFFIC_MB_GOAL = 20         # 每个账号下载的目标流量 (MB)
ONLINE_TIME_MINUTES = 10     # 每个账号要求在线时长 (分钟)
LOG_FILE = "dial_final_log.txt"
DOWNLOAD_DIR = "downloads"   # 下载文件存放根目录
DIAL_ERROR_FILE = "dial_failures.txt"
TRAFFIC_ERROR_FILE = "traffic_failures.txt"

def log(message):
    timestamp = time.strftime("%H:%M:%S")
    full_msg = f"[{timestamp}] {message}"
    print(full_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")

def record_error(file_path, user, pwd, reason):
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"{user},{pwd},{reason},{time.strftime('%Y-%m-%d %H:%M:%S')}\n")

def get_file_path(title):
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(title=title, filetypes=[("Text", "*.txt")])
    root.destroy()
    return path

def dial(user, password):
    cmd = f'rasdial "{ADSL_NAME}" {user} {password}'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        return True, "OK"
    return False, res.stdout.strip() or res.stderr.strip()

def disconnect():
    log("正在执行断开连接操作...")
    subprocess.run(f'rasdial "{ADSL_NAME}" /disconnect', shell=True, capture_output=True)

def download_video_task(urls, mb_goal, user, pwd):
    user_dir = os.path.join(DOWNLOAD_DIR, user)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)

    downloaded_bytes = 0
    goal_bytes = mb_goal * 1024 * 1024
    log(f"开始真实下行任务，目标: {mb_goal}MB...")

    with requests.Session() as session:
        session.verify = False
        try:
            while downloaded_bytes < goal_bytes:
                for url in urls:
                    url = url.strip()
                    if not url.startswith("http"): continue
                    file_name = f"video_{int(time.time())}.mp4"
                    save_path = os.path.join(user_dir, file_name)

                    with session.get(url, stream=True, timeout=20) as r:
                        r.raise_for_status()
                        with open(save_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=128 * 1024):
                                if chunk:
                                    f.write(chunk)
                                    downloaded_bytes += len(chunk)
                                    if downloaded_bytes >= goal_bytes:
                                        break
                    if downloaded_bytes >= goal_bytes: break

            log(f"✅ 流量任务已达成 ({downloaded_bytes / (1024*1024):.2f} MB)")
            return True
        except Exception as e:
            err_msg = f"流量下载过程异常: {str(e)}"
            log(f"❌ {err_msg}")
            record_error(TRAFFIC_ERROR_FILE, user, pwd, err_msg)
            return False

def main():
    print("=== 宽带批量拨号定时在线版 V4.6 ===")

    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    account_file = get_file_path("1. 请选择账号文件 (.txt)")
    if not account_file: return

    url_file = get_file_path("2. 请选择视频/大文件网址文件 (.txt)")
    target_urls = []
    if url_file:
        with open(url_file, "r", encoding="utf-8") as f:
            target_urls = [line.strip() for line in f if line.strip()]

    if not target_urls:
        print("未检测到网址文件，程序将退出。")
        return

    while True:
        with open(account_file, "r", encoding="utf-8") as f:
            accounts = [line.strip().split(",") for line in f if "," in line]

        log(f"总计加载 {len(accounts)} 个账号，开始执行任务...")

        for user, pwd in accounts:
            log(f"\n" + "="*40)
            log(f"当前操作账号: {user}")

            # 确保开始前是断开状态
            disconnect()
            time.sleep(2)

            # 1. 执行拨号
            success, msg = dial(user, pwd)
            if success:
                # 记录拨号成功的时间点
                dial_start_time = time.time()
                log("✅ 拨号成功！")

                # 2. 执行下行流量任务
                time.sleep(3)
                download_video_task(target_urls, TRAFFIC_MB_GOAL, user, pwd)

                # 3. 在线时长补足逻辑
                # 计算已经过去的时间（秒）
                elapsed_time = time.time() - dial_start_time
                required_seconds = ONLINE_TIME_MINUTES * 60

                if elapsed_time < required_seconds:
                    remaining_seconds = int(required_seconds - elapsed_time)
                    log(f"⏳ 流量任务已完成，但在线时长未达标。")
                    log(f"⏳ 仍需保持在线 {remaining_seconds} 秒 (约 {remaining_seconds/60:.1f} 分钟)...")
                    # 这里会阻塞直到满 10 分钟
                    time.sleep(remaining_seconds)

                log(f"⏰ 在线时长已满 {ONLINE_TIME_MINUTES} 分钟。")

                # 4. 手动断开连接
                disconnect()
                log(f"✅ 账号 {user} 流程全部结束。")
            else:
                log(f"🔺 拨号失败: {user} | 错误: {msg}")
                record_error(DIAL_ERROR_FILE, user, pwd, f"拨号错误: {msg}")

            # 账号切换间的短暂休息
            time.sleep(2)

        op = input("\n[一轮结束] 'r'重跑 / 'q'退出 / 'c'清空已下载视频: ")
        if op.lower() == 'c':
            shutil.rmtree(DOWNLOAD_DIR)
            os.makedirs(DOWNLOAD_DIR)
            print("已清空下载目录。")
        elif op.lower() == 'q':
            break

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"程序运行致命错误: {e}")
        input("按回车键退出...")
