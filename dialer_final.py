import subprocess
import time
import requests
import os
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import base64
from datetime import datetime

# --- 核心设置 ---
ADSL_NAME = "宽带连接"
TRAFFIC_MB_GOAL = 5
LOG_FILE = "dial_final_log.txt"
ERROR_FILE = "traffic_exceptions.txt"
LICENSE_FILE = "license.txt"
SECRET_SALT = "MySecretKey2026"  # 用于简单的校验加盐，可以随意修改

# --- 授权验证逻辑 ---

def get_network_time():
    """获取网络时间，防止修改系统时钟绕过验证"""
    try:
        # 通过请求大型网站获取响应头的日期信息
        response = requests.get("http://www.baidu.com", timeout=5)
        date_str = response.headers['date']
        # 转换格式: Tue, 27 Jan 2026 12:00:00 GMT
        net_date = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S GMT')
        return net_date
    except:
        return None

def verify_code(auth_code):
    """
    简单的授权码逻辑：
    假设授权码明文格式为 "YYYYMMDD" (过期日期)
    密文为 base64(日期 + 盐)
    """
    try:
        decoded_bytes = base64.b64decode(auth_code.encode('utf-8'))
        decoded_str = decoded_bytes.decode('utf-8')

        # 移除盐值获取日期
        if SECRET_SALT not in decoded_str:
            return False, "无效的授权码"

        expiry_date_str = decoded_str.replace(SECRET_SALT, "")
        expiry_date = datetime.strptime(expiry_date_str, "%Y%m%d")

        # 获取真实网络时间
        current_date = get_network_time()
        if not current_date:
            return False, "验证失败：无法连接到互联网校验时间"

        if current_date > expiry_date:
            return False, f"授权已过期 (过期时间: {expiry_date_str})"

        return True, expiry_date_str
    except:
        return False, "解析授权码失败"

def check_auth_on_startup():
    """启动时的授权检查流"""
    auth_code = ""
    if os.path.exists(LICENSE_FILE):
        with open(LICENSE_FILE, "r") as f:
            auth_code = f.read().strip()

    if not auth_code:
        root = tk.Tk()
        root.withdraw()
        auth_code = simpledialog.askstring("授权验证", "请输入您的授权码:")
        if not auth_code:
            return False

    is_valid, msg = verify_code(auth_code)
    if is_valid:
        with open(LICENSE_FILE, "w") as f:
            f.write(auth_code)
        print(f"✅ 授权验证通过！有效期至: {msg}")
        return True
    else:
        messagebox.showerror("授权错误", msg)
        if os.path.exists(LICENSE_FILE):
            os.remove(LICENSE_FILE)
        return False

# --- 原有拨号与流量逻辑 (保持不变) ---

def log(message):
    timestamp = time.strftime("%H:%M:%S")
    full_msg = f"[{timestamp}] {message}"
    print(full_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")

def record_error(user, pwd, reason):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(ERROR_FILE, "a", encoding="utf-8") as f:
        f.write(f"{user},{pwd},{reason},{timestamp}\n")

def dial(user, password):
    cmd = f'rasdial "{ADSL_NAME}" {user} {password}'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        return True, "Success"
    else:
        err_msg = res.stdout.strip() if res.stdout else "Unknown Dial Error"
        return False, err_msg.replace("\n", " ")

def generate_traffic(urls, mb_goal, user, pwd):
    downloaded_bytes = 0
    goal_bytes = mb_goal * 1024 * 1024
    log(f"开始流量任务: {mb_goal}MB...")
    try:
        while downloaded_bytes < goal_bytes:
            for url in urls:
                url = url.strip()
                if not url.startswith("http"): continue
                with requests.get(url, stream=True, timeout=15, verify=False) as r:
                    r.raise_for_status()
                    for chunk in r.iter_content(chunk_size=32768):
                        if chunk:
                            downloaded_bytes += len(chunk)
                            if downloaded_bytes >= goal_bytes: break
                if downloaded_bytes >= goal_bytes: break
        log(f"✅ 流量完成: {downloaded_bytes / (1024*1024):.2f} MB")
        return True
    except Exception as e:
        record_error(user, pwd, str(e))
        return False

def main():
    # 执行授权检查
    if not check_auth_on_startup():
        print("❌ 授权验证未通过，程序关闭。")
        time.sleep(3)
        return

    print("=== 宽带批量拨号(授权版) V5.0 ===")

    root = tk.Tk()
    root.withdraw()
    account_file = filedialog.askopenfilename(title="选择账号文件", filetypes=[("Text", "*.txt")])
    if not account_file: return

    url_file = filedialog.askopenfilename(title="选择网址文件", filetypes=[("Text", "*.txt")])
    target_urls = []
    if url_file:
        with open(url_file, "r", encoding="utf-8") as f:
            target_urls = [line.strip() for line in f if line.strip()]

    if not target_urls:
        manual_url = simpledialog.askstring("输入网址", "请输入默认网址:")
        if not manual_url: return
        target_urls = [manual_url]

    while True:
        with open(account_file, "r", encoding="utf-8") as f:
            accounts = [line.strip().split(",") for line in f if "," in line]

        for user, pwd in accounts:
            log(f"\n>>> 切换账号: {user}")
            subprocess.run(f'rasdial "{ADSL_NAME}" /disconnect', shell=True, capture_output=True)
            time.sleep(2)
            success, msg = dial(user, pwd)
            if success:
                log("✅ 拨号成功！")
                time.sleep(3)
                generate_traffic(target_urls, TRAFFIC_MB_GOAL, user, pwd)
            else:
                log(f"🔺 拨号失败: {msg}")
                record_error(user, pwd, f"拨号失败: {msg}")
            time.sleep(1)

        op = input("\n[一轮结束] 'r'重跑 / 'q'退出: ")
        if op.lower() == 'q': break

if __name__ == "__main__":
    main()