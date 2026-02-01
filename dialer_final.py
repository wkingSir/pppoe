import subprocess
import time
import requests
import os
import shutil
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import base64
from datetime import datetime, timedelta

# --- 核心配置 ---
ADSL_NAME = "宽带连接"
TRAFFIC_MB_GOAL = 5
LOG_FILE = "dial_final_log.txt"
DOWNLOAD_DIR = "downloads"
DIAL_ERROR_FILE = "dial_failures.txt"
TRAFFIC_ERROR_FILE = "traffic_failures.txt"
LICENSE_FILE = "license.txt"
SECRET_SALT = "ADSL_PRO_V45_SALT" # 必须与生成器一致

# --- 授权验证系统 ---

def get_machine_code():
    """获取本机的唯一 BIOS UUID"""
    try:
        # 仅限 Windows 运行
        cmd = "wmic csproduct get uuid"
        output = subprocess.check_output(cmd, shell=True).decode().split('\n')[1].strip()
        return output
    except:
        import uuid
        return str(uuid.getnode())

def get_network_time():
    """从网络获取当前日期，防止修改系统时间绕过授权"""
    try:
        # 使用百度响应头获取日期
        response = requests.get("http://www.baidu.com", timeout=5)
        date_str = response.headers['date']
        net_date = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S GMT')
        # 转换为东八区（加8小时北京时间，简单处理直接用日期比较即可）
        return net_date
    except:
        return None

def verify_auth(auth_code):
    """验证授权码：解密并匹配 [日期 + 机器码 + 盐]"""
    try:
        local_mid = get_machine_code()
        # 解密
        decoded_str = base64.b64decode(auth_code.encode('utf-8')).decode('utf-8')

        if SECRET_SALT not in decoded_str:
            return False, "非法授权码"

        # 拆分数据
        clean_data = decoded_str.replace(SECRET_SALT, "")
        expiry_date_str = clean_data[:8]  # 前8位是日期 YYYYMMDD
        code_mid = clean_data[8:]         # 后面是机器码

        # 1. 校验机器码
        if local_mid != code_mid:
            return False, "授权码与本机不匹配"

        # 2. 校验时间
        expiry_date = datetime.strptime(expiry_date_str, "%Y%m%d")
        current_date = get_network_time()

        if not current_date:
            return False, "验证失败：请检查网络连接以同步授权时间"

        if current_date > expiry_date:
            return False, f"授权已过期 (过期日期: {expiry_date_str})"

        return True, expiry_date_str
    except:
        return False, "授权码解析失败"

def check_license_flow():
    """启动时的授权检查流程"""
    local_mid = get_machine_code()
    auth_code = ""

    if os.path.exists(LICENSE_FILE):
        with open(LICENSE_FILE, "r") as f:
            auth_code = f.read().strip()

    if not auth_code:
        # 弹窗提示机器码并输入授权码
        root = tk.Tk()
        root.withdraw()
        # 自动复制机器码到剪贴板方便用户发送
        root.clipboard_clear()
        root.clipboard_append(local_mid)
        messagebox.showinfo("授权提示", f"您的机器码已复制:\n{local_mid}\n\n请联系管理员获取授权码。")

        auth_code = simpledialog.askstring("软件激活", "请输入授权码:")
        root.destroy()
        if not auth_code: return False

    valid, result = verify_auth(auth_code)
    if valid:
        with open(LICENSE_FILE, "w") as f:
            f.write(auth_code)
        print(f"✅ 激活成功！有效期至: {result}")
        return True
    else:
        messagebox.showerror("激活失败", result)
        if os.path.exists(LICENSE_FILE): os.remove(LICENSE_FILE)
        return False

# --- 拨号与下载逻辑 (你原有的代码) ---

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
    if res.returncode == 0: return True, "OK"
    return False, res.stdout.strip() or res.stderr.strip()

def disconnect():
    subprocess.run(f'rasdial "{ADSL_NAME}" /disconnect', shell=True, capture_output=True)

def download_video_task(urls, mb_goal, user, pwd):
    user_dir = os.path.join(DOWNLOAD_DIR, user)
    if not os.path.exists(user_dir): os.makedirs(user_dir)
    downloaded_bytes = 0
    goal_bytes = mb_goal * 1024 * 1024
    with requests.Session() as session:
        session.verify = False
        try:
            while downloaded_bytes < goal_bytes:
                for url in urls:
                    url = url.strip()
                    if not url.startswith("http"): continue
                    save_path = os.path.join(user_dir, f"v_{int(time.time())}.mp4")
                    with session.get(url, stream=True, timeout=20) as r:
                        r.raise_for_status()
                        with open(save_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=128 * 1024):
                                if chunk:
                                    f.write(chunk)
                                    downloaded_bytes += len(chunk)
                                    if downloaded_bytes >= goal_bytes: break
                    if downloaded_bytes >= goal_bytes: break
            log(f"✅ 账号 {user} 流量达标: {downloaded_bytes/(1024*1024):.2f} MB")
            return True
        except Exception as e:
            record_error(TRAFFIC_ERROR_FILE, user, pwd, str(e))
            return False

def main():
    # --- 授权检查 ---
    if not check_license_flow():
        return

    print("=== 宽带批量拨号视频下载版 V4.5 (授权版) ===")
    if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

    account_file = get_file_path("1. 请选择账号文件 (.txt)")
    if not account_file: return
    url_file = get_file_path("2. 请选择视频/大文件网址文件 (.txt)")
    if not url_file: return

    with open(url_file, "r", encoding="utf-8") as f:
        target_urls = [line.strip() for line in f if line.strip()]

    while True:
        with open(account_file, "r", encoding="utf-8") as f:
            accounts = [line.strip().split(",") for line in f if "," in line]

        for user, pwd in accounts:
            log(f"\n>>> 切换账号: {user}")
            disconnect()
            time.sleep(2)
            success, msg = dial(user, pwd)
            if success:
                log("✅ 拨号成功！准备下载...")
                time.sleep(3)
                download_video_task(target_urls, TRAFFIC_MB_GOAL, user, pwd)
            else:
                log(f"🔺 拨号失败: {user}")
                record_error(DIAL_ERROR_FILE, user, pwd, f"拨号错误: {msg}")
            time.sleep(1)

        op = input("\n[一轮结束] 'r'重跑 / 'q'退出 / 'c'清空视频: ")
        if op.lower() == 'c':
            shutil.rmtree(DOWNLOAD_DIR); os.makedirs(DOWNLOAD_DIR)
        elif op.lower() == 'q': break

if __name__ == "__main__":
    main()