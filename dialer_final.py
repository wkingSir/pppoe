import subprocess
import time
import requests
import os
import tkinter as tk
from tkinter import filedialog, simpledialog

# --- 核心设置 ---
ADSL_NAME = "宽带连接"
TRAFFIC_MB_GOAL = 2  # 每个账号产生的流量目标 (MB)
LOG_FILE = "dial_final_log.txt"
ERROR_FILE = "traffic_exceptions.txt"  # <--- 新增：异常记录文件

def log(message):
    timestamp = time.strftime("%H:%M:%S")
    full_msg = f"[{timestamp}] {message}"
    print(full_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")

def record_error(user, pwd, reason):
    """专门记录异常账号信息"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(ERROR_FILE, "a", encoding="utf-8") as f:
        # 格式：账号, 密码, 异常原因, 时间
        f.write(f"{user},{pwd},{reason},{timestamp}\n")

def get_file_path(title, file_types):
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(title=title, filetypes=file_types)
    return path

def dial(user, password):
    # 捕获输出以获取更详细的错误信息
    cmd = f'rasdial "{ADSL_NAME}" {user} {password}'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        return True, "Success"
    else:
        # 返回具体的 Windows 拨号错误信息
        err_msg = res.stdout.strip() if res.stdout else "Unknown Dial Error"
        return False, err_msg.replace("\n", " ")

def disconnect():
    subprocess.run(f'rasdial "{ADSL_NAME}" /disconnect', shell=True, capture_output=True)

def generate_traffic(urls, mb_goal, user, pwd):
    downloaded_bytes = 0
    goal_bytes = mb_goal * 1024 * 1024
    log(f"开始流量任务，目标: {mb_goal}MB...")

    # 记录是否成功产生过流量
    ever_downloaded = False

    try:
        while downloaded_bytes < goal_bytes:
            for url in urls:
                url = url.strip()
                if not url.startswith("http"): continue

                log(f"正在读取: {url}")
                try:
                    # 使用 stream=True 确保产生真实下行流量
                    with requests.get(url, stream=True, timeout=15, verify=False) as r:
                        r.raise_for_status() # 检查 HTTP 状态码
                        for chunk in r.iter_content(chunk_size=32768): # 32KB 块
                            if chunk:
                                downloaded_bytes += len(chunk)
                                ever_downloaded = True
                                if downloaded_bytes >= goal_bytes: break
                except Exception as site_err:
                    # 单个网址访问失败仅记录日志，不终止整个任务
                    log(f"⚠️ 网址访问异常 ({url}): {type(site_err).__name__}")

                if downloaded_bytes >= goal_bytes: break

            # 如果跑完一遍所有网址，一点流量都没产生，说明网络虽然通了但访问受限
            if not ever_downloaded:
                raise Exception("拨号成功但无法从任何指定网址获取数据(网络质量差或被拦截)")

            # 防止死循环（如果所有网址都挂了）
            if not downloaded_bytes >= goal_bytes and not ever_downloaded:
                break

        log(f"✅ 流量达标: {downloaded_bytes / (1024*1024):.2f} MB")
        return True
    except Exception as e:
        error_reason = f"流量产生阶段异常: {str(e)}"
        log(f"❌ {error_reason}")
        record_error(user, pwd, error_reason) # <--- 记录到异常文件
        return False

def main():
    print("=== 宽带批量拨号(全动态配置版) V4.1 ===")

    account_file = get_file_path("1. 请选择账号文件 (.txt)", [("Text", "*.txt")])
    if not account_file: return

    url_file = get_file_path("2. 请选择目标网址文件 (.txt)", [("Text", "*.txt")])

    target_urls = []
    if url_file:
        with open(url_file, "r", encoding="utf-8") as f:
            target_urls = [line.strip() for line in f if line.strip()]

    if not target_urls:
        root = tk.Tk()
        root.withdraw()
        manual_url = simpledialog.askstring("输入网址", "未检测到网址文件，请输入一个默认访问地址:")
        if not manual_url: return
        target_urls = [manual_url]

    log(f"配置完成：账号文件({os.path.basename(account_file)}), 目标网址({len(target_urls)}个)")

    while True:
        if not os.path.exists(account_file):
            log("账号文件丢失！")
            break

        with open(account_file, "r", encoding="utf-8") as f:
            accounts = [line.strip().split(",") for line in f if "," in line]

        log(f"已加载 {len(accounts)} 个账号，准备开始...")

        for user, pwd in accounts:
            log(f"\n>>> 切换账号: {user}")
            disconnect()
            time.sleep(2)

            success, msg = dial(user, pwd)
            if success:
                log("✅ 拨号成功！")
                time.sleep(3) # 等待网络稳定
                # 传入 user 和 pwd 用于记录异常
                generate_traffic(target_urls, TRAFFIC_MB_GOAL, user, pwd)
            else:
                reason = f"拨号失败: {msg}"
                log(f"🔺 {reason}")
                # <--- 拨号不成功也记录到异常文件
                record_error(user, pwd, reason)

            time.sleep(1)

        op = input("\n[一轮结束] 'r'重跑 / 'q'退出: ")
        if op.lower() == 'q': break

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"程序关键错误: {e}")
        input("按回车键退出...")