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
LOG_FILE = "dial_final_log.txt"
DOWNLOAD_DIR = "downloads"  # 下载文件存放根目录
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
    root.destroy() # 显式销毁资源，防止线程残留
    return path

def dial(user, password):
    # 使用 rasdial 进行拨号
    cmd = f'rasdial "{ADSL_NAME}" {user} {password}'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        return True, "OK"
    return False, res.stdout.strip() or res.stderr.strip()

def disconnect():
    subprocess.run(f'rasdial "{ADSL_NAME}" /disconnect', shell=True, capture_output=True)

def download_video_task(urls, mb_goal, user, pwd):
    """下载视频到用户专用文件夹，产生真实下行流量"""
    # 1. 创建用户专属文件夹
    user_dir = os.path.join(DOWNLOAD_DIR, user)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)

    downloaded_bytes = 0
    goal_bytes = mb_goal * 1024 * 1024
    log(f"开始真实下行任务，目标: {mb_goal}MB...")

    # 使用 Session 减少创建线程开销
    with requests.Session() as session:
        session.verify = False # 忽略SSL证书问题
        try:
            while downloaded_bytes < goal_bytes:
                for url in urls:
                    url = url.strip()
                    if not url.startswith("http"): continue

                    file_name = f"video_{int(time.time())}.mp4"
                    save_path = os.path.join(user_dir, file_name)

                    log(f"正在从网址下载: {url[:50]}...")

                    with session.get(url, stream=True, timeout=20) as r:
                        r.raise_for_status()
                        # 真实写入磁盘
                        with open(save_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=128 * 1024): # 128KB块
                                if chunk:
                                    f.write(chunk)
                                    downloaded_bytes += len(chunk)
                                    # 实时检测是否达标
                                    if downloaded_bytes >= goal_bytes:
                                        break
                    if downloaded_bytes >= goal_bytes: break

            log(f"✅ 账号 {user} 流量达标: {downloaded_bytes / (1024*1024):.2f} MB")
            return True
        except Exception as e:
            err_msg = f"流量异常: {str(e)}"
            log(f"❌ {err_msg}")
            record_error(TRAFFIC_ERROR_FILE, user, pwd, err_msg)
            return False

def main():
    print("=== 宽带批量拨号视频下载版 V4.5 ===")

    # 初始化
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

        log(f"总计加载 {len(accounts)} 个账号，开始循环拨号任务...")

        for user, pwd in accounts:
            log(f"\n>>> 切换账号: {user}")
            disconnect()
            time.sleep(2)

            # 拨号测试
            success, msg = dial(user, pwd)
            if success:
                log("✅ 拨号成功！准备下载视频...")
                time.sleep(3) # 等待网络稳定
                # 下载视频产生流量
                download_video_task(target_urls, TRAFFIC_MB_GOAL, user, pwd)
            else:
                log(f"🔺 拨号失败: {user}")
                record_error(DIAL_ERROR_FILE, user, pwd, f"拨号错误: {msg}")

            time.sleep(1)

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
