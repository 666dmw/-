import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import re
import json
import threading

CONFIG_FILE = "strm_config.json"

# 保存配置
def save_config(data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 读取配置
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# 提取季编号，格式化为 Season XX
def extract_season(file):
    match = re.search(r"S(\d{2})|Season[ ._]?(\d{1,2})", file, re.IGNORECASE)
    if match:
        season_num = match.group(1) or match.group(2)
        return f"Season {int(season_num):02d}"
    return "Season 未知"

# 递归收集 .strm 文件
def collect_strm_files(folder):
    all_files = []
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(".strm"):
                full_path = os.path.join(root, f)
                all_files.append(full_path)
    return all_files

class StrmOrganizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("STRM 剧集整理工具（含预览与分类）")
        self.config = load_config()

        self.src_path = tk.StringVar(value=self.config.get("src_path", ""))
        self.dst_path = tk.StringVar(value=self.config.get("dst_path", ""))

        self.preview_data = []  # (src_path, dst_path)

        self.setup_ui()

    def setup_ui(self):
        frm = ttk.Frame(self.root, padding=10)
        frm.grid(sticky="nsew")

        row = 0
        ttk.Label(frm, text="来源目录:").grid(row=row, column=0, sticky='e')
        ttk.Entry(frm, textvariable=self.src_path, width=50).grid(row=row, column=1)
        ttk.Button(frm, text="选择", command=self.select_src).grid(row=row, column=2)

        row += 1
        ttk.Label(frm, text="目标目录:").grid(row=row, column=0, sticky='e')
        ttk.Entry(frm, textvariable=self.dst_path, width=50).grid(row=row, column=1)
        ttk.Button(frm, text="选择", command=self.select_dst).grid(row=row, column=2)

        row += 1
        ttk.Button(frm, text="扫描并预览", command=self.preview_files).grid(row=row, column=1, pady=10)

        row += 1
        ttk.Label(frm, text="复制预览（可多选取消）:").grid(row=row, column=0, sticky='ne')
        self.listbox = tk.Listbox(frm, selectmode=tk.MULTIPLE, width=90, height=12)
        self.listbox.grid(row=row, column=1, columnspan=2)

        row += 1
        ttk.Button(frm, text="开始复制选中项", command=self.start_copy).grid(row=row, column=1, pady=10)

        row += 1
        ttk.Label(frm, text="操作日志:").grid(row=row, column=0, sticky="ne")
        self.log_text = tk.Text(frm, height=8, width=70)
        self.log_text.grid(row=row, column=1, columnspan=2)

        row += 1
        ttk.Label(frm, text="进度:").grid(row=row, column=0, sticky="e")
        self.progress = ttk.Progressbar(frm, length=300, mode="determinate")
        self.progress.grid(row=row, column=1, columnspan=2, sticky="w")

    def select_src(self):
        path = filedialog.askdirectory()
        if path:
            self.src_path.set(path)

    def select_dst(self):
        path = filedialog.askdirectory()
        if path:
            self.dst_path.set(path)

    def preview_files(self):
        self.listbox.delete(0, tk.END)
        self.preview_data.clear()

        src = self.src_path.get()
        dst = self.dst_path.get()

        if not os.path.isdir(src):
            messagebox.showerror("错误", "无效的来源目录")
            return

        files = collect_strm_files(src)

        for f in files:
            season = extract_season(os.path.basename(f))
            season_dir = os.path.join(dst, season)
            target_path = os.path.join(season_dir, os.path.basename(f))
            display = f"{f}  →  {target_path}"
            self.listbox.insert(tk.END, display)
            self.preview_data.append((f, target_path))

    def start_copy(self):
        threading.Thread(target=self._copy_files).start()

    def _copy_files(self):
        selected_indices = self.listbox.curselection()
        if not selected_indices:
            selected_indices = list(range(len(self.preview_data)))

        to_copy = [self.preview_data[i] for i in selected_indices]
        self.progress["maximum"] = len(to_copy)
        self.progress["value"] = 0
        self.log_text.delete(1.0, tk.END)

        copied = 0
        for i, (src, dst) in enumerate(to_copy):
            self.progress["value"] = i + 1
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                if not os.path.exists(dst):
                    shutil.copy2(src, dst)
                    self.log(f"复制: {src} → {dst}")
                    copied += 1
                else:
                    self.log(f"跳过: 已存在 {dst}")
            except Exception as e:
                self.log(f"失败: {src} → {e}")

        save_config({"src_path": self.src_path.get(), "dst_path": self.dst_path.get()})
        messagebox.showinfo("完成", f"共复制 {copied} 个文件。")

    def log(self, text):
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = StrmOrganizerApp(root)
    root.mainloop()