import subprocess
import time
import requests
import os
import tkinter as tk
from tkinter import filedialog, simpledialog

# --- 核心设置 ---
ADSL_NAME = "宽带连接"
TRAFFIC_MB_GOAL = 5  # 每个账号产生的流量目标 (MB)
LOG_FILE = "dial_final_log.txt"

def log(message):
    timestamp = time.strftime("%H:%M:%S")
    full_msg = f"[{timestamp}] {message}"
    print(full_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")

def get_file_path(title, file_types):
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(title=title, filetypes=file_types)
    return path

def dial(user, password):
    cmd = f'rasdial "{ADSL_NAME}" {user} {password}'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.returncode == 0

def disconnect():
    subprocess.run(f'rasdial "{ADSL_NAME}" /disconnect', shell=True, capture_output=True)

def generate_traffic(urls, mb_goal):
    downloaded_bytes = 0
    goal_bytes = mb_goal * 1024 * 1024
    log(f"开始流量任务，目标: {mb_goal}MB...")
    
    try:
        while downloaded_bytes < goal_bytes:
            for url in urls:
                url = url.strip()
                if not url.startswith("http"): continue
                
                log(f"正在读取: {url}")
                # 使用 stream=True 确保产生真实下行流量
                with requests.get(url, stream=True, timeout=15, verify=False) as r:
                    for chunk in r.iter_content(chunk_size=16384): # 16KB 块读取
                        if chunk:
                            downloaded_bytes += len(chunk)
                            if downloaded_bytes >= goal_bytes: break
                if downloaded_bytes >= goal_bytes: break
        log(f"✅ 流量达标: {downloaded_bytes / (1024*1024):.2f} MB")
        return True
    except Exception as e:
        log(f"❌ 流量异常: {e}")
        return False

def main():
    print("=== 宽带批量拨号(全动态配置版) V4.0 ===")
    
    # 1. 运行时加载账号文件
    account_file = get_file_path("1. 请选择账号文件 (.txt)", [("Text", "*.txt")])
    if not account_file: return

    # 2. 运行时加载网址文件
    url_file = get_file_path("2. 请选择目标网址文件 (.txt)", [("Text", "*.txt")])
    
    target_urls = []
    if url_file:
        with open(url_file, "r", encoding="utf-8") as f:
            target_urls = [line.strip() for line in f if line.strip()]
    
    # 如果没选文件，则手动输入一个
    if not target_urls:
        root = tk.Tk()
        root.withdraw()
        manual_url = simpledialog.askstring("输入网址", "未检测到网址文件，请输入一个默认访问地址:")
        if not manual_url: return
        target_urls = [manual_url]

    log(f"配置完成：账号文件({os.path.basename(account_file)}), 目标网址({len(target_urls)}个)")

    while True:
        with open(account_file, "r", encoding="utf-8") as f:
            accounts = [line.strip().split(",") for line in f if "," in line]
        
        for user, pwd in accounts:
            log(f"\n>>> 切换账号: {user}")
            disconnect()
            time.sleep(2)

            if dial(user, pwd):
                log("✅ 拨号成功！")
                time.sleep(3) # 等待网络稳定
                generate_traffic(target_urls, TRAFFIC_MB_GOAL)
            else:
                log(f"🔺 拨号失败: {user}")
            
            time.sleep(1)

        op = input("\n[一轮结束] 'r'重跑 / 'q'退出: ")
        if op.lower() == 'q': break

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"程序运行出错: {e}")
        input("按回车键退出...")
