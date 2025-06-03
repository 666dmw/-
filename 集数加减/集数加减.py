import os
import re
import shutil
import threading
import json
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter.ttk import Progressbar

CONFIG_FILE = "config.json"
LOG_FILE = "operation_log.json"

def find_episodes(root_dir, exts=None):
    if exts is None:
        exts = ['.mp4', '.mkv', '.avi', '.mov', '.wmv']
    exts = [e.lower() for e in exts]
    matches = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if any(f.lower().endswith(ext) for ext in exts):
                matches.append(os.path.join(dirpath, f))
    return matches

def parse_episode_number(filename):
    """
    支持多种格式：
    - S01E05 或 s01e05
    - E05 或 Ep05
    - 第5集 / 第05集 / 第5话 / 第05话 / 第5回 等
    """
    patterns = [
        re.compile(r'[Ss](\d+)[Ee](\d+)'),       # S01E05
        re.compile(r'[Ee][Pp]?(\d+)'),          # E05, Ep05
        re.compile(r'第0*(\d+)[集话回]'),         # 第5集，第05话，第5回
    ]
    for p in patterns:
        m = p.search(filename)
        if m:
            if len(m.groups()) == 2:
                season = int(m.group(1))
                episode = int(m.group(2))
                return season, episode
            elif len(m.groups()) == 1:
                return 0, int(m.group(1))
    return None

def replace_episode_number(filename, season, episode):
    sxe_pattern = re.compile(r'[Ss](\d+)[Ee](\d+)')
    if sxe_pattern.search(filename):
        return sxe_pattern.sub(f"S{season:02d}E{episode:02d}", filename)

    e_pattern = re.compile(r'[Ee][Pp]?(\d+)')
    if e_pattern.search(filename):
        return e_pattern.sub(f"E{episode:02d}", filename)

    cn_pattern = re.compile(r'第0*\d+[集话回]')
    if cn_pattern.search(filename):
        # 替换成“第X集”，固定格式，方便识别
        return cn_pattern.sub(f"第{episode}集", filename)

    # 找不到匹配就返回原文件名
    return filename

class BatchEpisodeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("剧集集数批量加减（复制改名） - 支持撤销和进度条")
        self.root.geometry("800x550")

        # 操作记录，用于撤销，格式：[{"src":原文件, "dst":复制文件}]
        self.operation_log = []

        # UI布局
        tk.Label(root, text="源目录：").grid(row=0, column=0, sticky="e")
        self.src_entry = tk.Entry(root, width=65)
        self.src_entry.grid(row=0, column=1, padx=5, pady=5)
        tk.Button(root, text="选择", command=self.select_src).grid(row=0, column=2, padx=5)

        tk.Label(root, text="目标目录：").grid(row=1, column=0, sticky="e")
        self.dst_entry = tk.Entry(root, width=65)
        self.dst_entry.grid(row=1, column=1, padx=5, pady=5)
        tk.Button(root, text="选择", command=self.select_dst).grid(row=1, column=2, padx=5)

        tk.Label(root, text="集数加减值：").grid(row=2, column=0, sticky="e")
        self.delta_entry = tk.Entry(root, width=10)
        self.delta_entry.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        tk.Label(root, text="（正数加，负数减）").grid(row=2, column=1, sticky="e", padx=5)

        tk.Label(root, text="自定义文件格式（扩展名，英文逗号分隔）：").grid(row=3, column=0, sticky="e")
        self.ext_entry = tk.Entry(root, width=65)
        self.ext_entry.grid(row=3, column=1, padx=5, pady=5)
        tk.Label(root, text="示例：.mp4,.mkv,.ts").grid(row=3, column=2, sticky="w")

        self.start_button = tk.Button(root, text="开始复制并改名", command=self.start_task)
        self.start_button.grid(row=4, column=1, pady=10, sticky="w")

        self.undo_button = tk.Button(root, text="撤销上一次操作", command=self.undo_last, state="disabled")
        self.undo_button.grid(row=4, column=1, pady=10, sticky="e")

        self.progress = Progressbar(root, orient='horizontal', length=700, mode='determinate')
        self.progress.grid(row=5, column=0, columnspan=3, padx=10)

        self.log_text = scrolledtext.ScrolledText(root, width=95, height=22, state='disabled')
        self.log_text.grid(row=6, column=0, columnspan=3, padx=10, pady=10)

        self.load_config()
        self.load_operation_log()

    def log(self, msg):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def select_src(self):
        path = filedialog.askdirectory()
        if path:
            self.src_entry.delete(0, tk.END)
            self.src_entry.insert(0, path)

    def select_dst(self):
        path = filedialog.askdirectory()
        if path:
            self.dst_entry.delete(0, tk.END)
            self.dst_entry.insert(0, path)

    def save_config(self):
        data = {
            "src": self.src_entry.get(),
            "dst": self.dst_entry.get(),
            "delta": self.delta_entry.get(),
            "exts": self.ext_entry.get(),
        }
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"保存配置失败：{e}")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.src_entry.insert(0, data.get("src", ""))
                self.dst_entry.insert(0, data.get("dst", ""))
                self.delta_entry.insert(0, data.get("delta", ""))
                self.ext_entry.insert(0, data.get("exts", ".mp4,.mkv,.avi,.mov,.wmv"))
            except Exception as e:
                self.log(f"加载配置失败: {e}")
        else:
            self.ext_entry.insert(0, ".mp4,.mkv,.avi,.mov,.wmv")

    def save_operation_log(self):
        try:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.operation_log, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"保存操作记录失败: {e}")

    def load_operation_log(self):
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    self.operation_log = json.load(f)
                if self.operation_log:
                    self.undo_button.config(state="normal")
                else:
                    self.undo_button.config(state="disabled")
            except Exception as e:
                self.log(f"加载操作记录失败: {e}")
                self.undo_button.config(state="disabled")
        else:
            self.undo_button.config(state="disabled")

    def batch_copy_and_rename(self, src_dir, dst_dir, delta, exts):
        files = find_episodes(src_dir, exts)
        self.log(f"找到 {len(files)} 个符合扩展名的文件。")
        self.progress['maximum'] = len(files)
        self.progress['value'] = 0

        self.operation_log.clear()

        count = 0
        for idx, f in enumerate(files, 1):
            rel_path = os.path.relpath(f, src_dir)
            new_dir = os.path.join(dst_dir, os.path.dirname(rel_path))
            os.makedirs(new_dir, exist_ok=True)

            parsed = parse_episode_number(os.path.basename(f))
            if not parsed:
                self.log(f"跳过未识别集数的文件: {f}")
                self.progress['value'] = idx
                continue
            season, episode = parsed
            new_episode = episode + delta
            if new_episode < 1:
                self.log(f"跳过调整后集数小于1的文件: {f}")
                self.progress['value'] = idx
                continue

            new_name = replace_episode_number(os.path.basename(f), season, new_episode)
            src_full_path = f
            dst_full_path = os.path.join(new_dir, new_name)

            try:
                shutil.copy2(src_full_path, dst_full_path)
                self.log(f"复制并重命名: {src_full_path} -> {dst_full_path}")
                count += 1
                # 记录操作
                self.operation_log.append({"src": src_full_path, "dst": dst_full_path})
            except Exception as e:
                self.log(f"复制失败: {src_full_path} -> {dst_full_path}，错误：{e}")

            self.progress['value'] = idx

        self.save_operation_log()
        self.undo_button.config(state="normal")
        self.log(f"操作完成！成功复制并重命名 {count} 个文件。")

    def start_task(self):
        src_dir = self.src_entry.get().strip()
        dst_dir = self.dst_entry.get().strip()
        delta_str = self.delta_entry.get().strip()
        exts_raw = self.ext_entry.get().strip()

        if not os.path.isdir(src_dir):
            messagebox.showerror("错误", "源目录无效或不存在！")
            return
        if not os.path.isdir(dst_dir):
            messagebox.showerror("错误", "目标目录无效或不存在！")
            return
        try:
            delta = int(delta_str)
        except:
            messagebox.showerror("错误", "集数加减值必须是整数！")
            return
        if not exts_raw:
            messagebox.showerror("错误", "请填写至少一个文件扩展名！")
            return

        # 处理扩展名输入
        exts = []
        for ext in exts_raw.split(','):
            ext = ext.strip().lower()
            if not ext.startswith('.'):
                ext = '.' + ext
            exts.append(ext)

        self.save_config()
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')
        self.progress['value'] = 0

        self.start_button.config(state="disabled")
        threading.Thread(target=self._thread_task, args=(src_dir, dst_dir, delta, exts), daemon=True).start()

    def _thread_task(self, src_dir, dst_dir, delta, exts):
        self.batch_copy_and_rename(src_dir, dst_dir, delta, exts)
        self.start_button.config(state="normal")

    def undo_last(self):
        if not self.operation_log:
            messagebox.showinfo("提示", "没有可撤销的操作。")
            self.undo_button.config(state="disabled")
            return

        failed = 0
        for op in self.operation_log:
            dst = op['dst']
            try:
                if os.path.exists(dst):
                    os.remove(dst)
                    self.log(f"撤销删除: {dst}")
                else:
                    self.log(f"撤销失败，文件不存在: {dst}")
                    failed += 1
            except Exception as e:
                self.log(f"撤销失败: {dst}，错误：{e}")
                failed += 1

        if failed == 0:
            messagebox.showinfo("撤销成功", "已成功撤销上一次操作。")
            self.operation_log.clear()
            self.save_operation_log()
            self.undo_button.config(state="disabled")
        else:
            messagebox.showwarning("部分撤销失败", f"部分文件未能成功删除，请检查日志。")

if __name__ == "__main__":
    root = tk.Tk()
    app = BatchEpisodeApp(root)
    root.mainloop()
