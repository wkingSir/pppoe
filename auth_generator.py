import tkinter as tk
from tkinter import messagebox
import base64
from datetime import datetime, timedelta

class AuthGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("宽带拨号工具 - 授权码生成器")
        self.root.geometry("400x350")

        # 盐值 (必须与主脚本中的 SECRET_SALT 一致)
        self.salt = "MySecretKey2026"

        # 界面布局
        tk.Label(root, text="授权码生成系统", font=("Arial", 16, "bold")).pack(pady=10)

        # 过期日期输入
        tk.Label(root, text="设置过期日期 (格式: YYYYMMDD):").pack(pady=5)
        self.date_entry = tk.Entry(root, font=("Arial", 12), justify='center')
        self.date_entry.pack(pady=5)

        # 默认设置一个月后
        default_date = (datetime.now() + timedelta(days=30)).strftime("%Y%m%d")
        self.date_entry.insert(0, default_date)

        # 快捷按钮
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="一个月", command=lambda: self.set_date(30)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="三个月", command=lambda: self.set_date(90)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="一年", command=lambda: self.set_date(365)).pack(side=tk.LEFT, padx=5)

        # 生成按钮
        tk.Button(root, text="生成并复制授权码", bg="#4CAF50", fg="white",
                  font=("Arial", 10, "bold"), command=self.generate).pack(pady=15, ipadx=10, ipady=5)

        # 结果显示
        self.result_var = tk.StringVar()
        self.result_entry = tk.Entry(root, textvariable=self.result_var, font=("Arial", 10), state='readonly', justify='center')
        self.result_entry.pack(pady=5, fill=tk.X, padx=20)

    def set_date(self, days):
        new_date = (datetime.now() + timedelta(days=days)).strftime("%Y%m%d")
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, new_date)

    def generate(self):
        date_str = self.date_entry.get().strip()

        # 验证日期格式
        try:
            datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            messagebox.showerror("错误", "日期格式不正确！请输入 YYYYMMDD，例如 20260227")
            return

        # 加密算法：Base64(日期 + 盐)
        raw_str = date_str + self.salt
        auth_code = base64.b64encode(raw_str.encode('utf-8')).decode('utf-8')

        self.result_var.set(auth_code)

        # 自动复制到剪贴板
        self.root.clipboard_clear()
        self.root.clipboard_append(auth_code)
        messagebox.showinfo("成功", f"授权码已生成并复制到剪贴板！\n过期日期: {date_str}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AuthGenerator(root)
    root.mainloop()