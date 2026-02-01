import tkinter as tk
from tkinter import messagebox
import base64
from datetime import datetime, timedelta

class GeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("拨号工具授权生成器")
        self.root.geometry("400x400")
        self.salt = "ADSL_PRO_V45_SALT" # 必须与主脚本一致

        tk.Label(root, text="机器码绑定授权系统", font=("Arial", 12, "bold")).pack(pady=10)

        tk.Label(root, text="1. 输入用户机器码:").pack()
        self.mid_input = tk.Entry(root, width=40)
        self.mid_input.pack(pady=5)

        tk.Label(root, text="2. 选择授权时长:").pack()
        self.duration = tk.IntVar(value=30)
        tk.Radiobutton(root, text="1个月 (30天)", variable=self.duration, value=30).pack()
        tk.Radiobutton(root, text="3个月 (90天)", variable=self.duration, value=90).pack()
        tk.Radiobutton(root, text="半年 (180天)", variable=self.duration, value=180).pack()

        tk.Button(root, text="生成并复制授权码", bg="green", fg="white", command=self.generate).pack(pady=20)

        self.res_output = tk.Entry(root, width=45, state='readonly')
        self.res_output.pack(pady=5)

    def generate(self):
        mid = self.mid_input.get().strip()
        if not mid:
            messagebox.showerror("错误", "请填写机器码")
            return

        # 计算过期日期
        expiry_date = (datetime.now() + timedelta(days=self.duration.get())).strftime("%Y%m%d")

        # 算法：Base64(过期日期 + 机器码 + 盐)
        raw_str = expiry_date + mid + self.salt
        auth_code = base64.b64encode(raw_str.encode('utf-8')).decode('utf-8')

        self.res_output.config(state='normal')
        self.res_output.delete(0, tk.END)
        self.res_output.insert(0, auth_code)
        self.res_output.config(state='readonly')

        self.root.clipboard_clear()
        self.root.clipboard_append(auth_code)
        messagebox.showinfo("成功", f"授权码已生成！\n过期日期：{expiry_date}\n已复制到剪贴板。")

if __name__ == "__main__":
    root = tk.Tk()
    GeneratorApp(root)
    root.mainloop()