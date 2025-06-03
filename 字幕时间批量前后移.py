import os
import re
import chardet
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
from datetime import datetime

def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        rawdata = f.read(10000)  # 读取前1万字节检测编码
    result = chardet.detect(rawdata)
    return result['encoding'] or 'utf-8'

def format_timestamp(ms_total, fmt):
    h, rem = divmod(ms_total, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)

    if fmt == 'srt':
        return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
    elif fmt == 'vtt':
        return f'{h:02d}:{m:02d}:{s:02d}.{ms:03d}'
    else:
        raise ValueError("不支持的字幕格式")

def parse_time_to_ms(timestamp, fmt):
    if fmt == 'srt':
        h, m, s_ms = timestamp.split(':')
        s, ms = s_ms.split(',')
    elif fmt == 'vtt':
        h, m, s_ms = timestamp.split(':')
        s, ms = s_ms.split('.')
    else:
        raise ValueError("不支持的字幕格式")
    return int(h)*3600000 + int(m)*60000 + int(s)*1000 + int(ms)

def shift_timestamp_line(line, shift_ms, fmt):
    start, end = line.strip().split(' --> ')
    start_ms = parse_time_to_ms(start, fmt) + shift_ms
    end_ms = parse_time_to_ms(end, fmt) + shift_ms

    start_ms = max(start_ms, 0)
    end_ms = max(end_ms, 0)

    return f"{format_timestamp(start_ms, fmt)} --> {format_timestamp(end_ms, fmt)}\n"

def process_subtitle(file_path, shift_seconds, output_dir):
    fmt = os.path.splitext(file_path)[-1].lower().lstrip('.')
    if fmt not in ['srt', 'vtt']:
        return None, "不支持的字幕格式"

    encoding = detect_encoding(file_path)

    with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
        lines = f.readlines()

    shift_ms = int(shift_seconds * 1000)
    output_lines = []
    preview_changes = []  # 用于预览原时间->新时间

    for line in lines:
        if '-->' in line:
            try:
                old_line = line.strip()
                new_line = shift_timestamp_line(line, shift_ms, fmt).strip()
                output_lines.append(new_line + '\n')
                preview_changes.append((old_line, new_line))
            except Exception as e:
                output_lines.append(line)
        else:
            output_lines.append(line)

    # 输出路径
    base_name = os.path.basename(file_path)
    out_path = os.path.join(output_dir, base_name)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)

    return preview_changes, None

def scan_subtitles(root_dir):
    matches = []
    for root, _, files in os.walk(root_dir):
        for f in files:
            if f.lower().endswith(('.srt', '.vtt')):
                matches.append(os.path.join(root, f))
    return matches

class SubtitleShiftApp:
    def __init__(self, root):
        self.root = root
        self.root.title("字幕时间轴批量调整工具")
        self.root.geometry("900x600")

        # 目录输入
        frame = tk.Frame(root)
        frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(frame, text="字幕文件夹路径：").pack(side=tk.LEFT)
        self.entry_input = tk.Entry(frame)
        self.entry_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(frame, text="选择文件夹", command=self.select_input_dir).pack(side=tk.LEFT)

        # 输出目录
        frame_out = tk.Frame(root)
        frame_out.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(frame_out, text="输出文件夹路径：").pack(side=tk.LEFT)
        self.entry_output = tk.Entry(frame_out)
        self.entry_output.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(frame_out, text="选择输出文件夹", command=self.select_output_dir).pack(side=tk.LEFT)

        # 时间偏移
        frame_shift = tk.Frame(root)
        frame_shift.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(frame_shift, text="时间偏移（秒，支持正负）：").pack(side=tk.LEFT)
        self.entry_shift = tk.Entry(frame_shift, width=10)
        self.entry_shift.pack(side=tk.LEFT, padx=5)

        # 文件列表
        frame_list = tk.Frame(root)
        frame_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.tree = ttk.Treeview(frame_list, columns=("path", "status"), selectmode="extended")
        self.tree.heading("#0", text="选择")
        self.tree.heading("path", text="文件路径")
        self.tree.heading("status", text="状态")
        self.tree.column("#0", width=50, anchor=tk.CENTER)
        self.tree.column("path", width=600)
        self.tree.column("status", width=100, anchor=tk.CENTER)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(frame_list, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # 预览文本框
        frame_preview = tk.LabelFrame(root, text="时间线调整预览（原时间 --> 新时间）")
        frame_preview.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.text_preview = scrolledtext.ScrolledText(frame_preview, height=10)
        self.text_preview.pack(fill=tk.BOTH, expand=True)

        # 按钮区
        frame_btn = tk.Frame(root)
        frame_btn.pack(fill=tk.X, padx=10, pady=5)

        tk.Button(frame_btn, text="扫描字幕文件", command=self.scan_files).pack(side=tk.LEFT)
        tk.Button(frame_btn, text="预览选中文件", command=self.preview_selected).pack(side=tk.LEFT, padx=10)
        tk.Button(frame_btn, text="开始批量处理", command=self.batch_process).pack(side=tk.LEFT)

        # 日志文件路径
        self.log_path = os.path.join(os.getcwd(), "字幕时间轴调整日志.log")

    def select_input_dir(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_input.delete(0, tk.END)
            self.entry_input.insert(0, folder)

    def select_output_dir(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_output.delete(0, tk.END)
            self.entry_output.insert(0, folder)

    def scan_files(self):
        input_dir = self.entry_input.get().strip()
        if not os.path.isdir(input_dir):
            messagebox.showerror("错误", "请输入有效的字幕文件夹路径")
            return
        files = scan_subtitles(input_dir)
        self.tree.delete(*self.tree.get_children())
        for f in files:
            self.tree.insert("", "end", iid=f, text="", values=(f, "未预览"))
            # 默认选中
            self.tree.selection_add(f)
        messagebox.showinfo("完成", f"扫描到 {len(files)} 个字幕文件")

    def preview_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择至少一个字幕文件")
            return
        shift_str = self.entry_shift.get().strip()
        try:
            shift_sec = float(shift_str)
        except:
            messagebox.showerror("错误", "请输入有效的数字时间偏移")
            return

        self.text_preview.delete("1.0", tk.END)

        for f in selected:
            preview, err = process_subtitle_preview(f, shift_sec)
            if err:
                self.tree.set(f, "status", f"预览失败: {err}")
                continue
            self.tree.set(f, "status", "已预览")
            self.text_preview.insert(tk.END, f"文件: {f}\n")
            for old, new in preview[:10]:  # 预览前10行时间改动
                self.text_preview.insert(tk.END, f"  {old}  -->  {new}\n")
            self.text_preview.insert(tk.END, "\n")

    def batch_process(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择至少一个字幕文件")
            return
        shift_str = self.entry_shift.get().strip()
        if not shift_str:
            messagebox.showerror("错误", "请输入时间偏移秒数")
            return
        try:
            shift_sec = float(shift_str)
        except:
            messagebox.showerror("错误", "请输入有效的时间偏移数值")
            return

        output_dir = self.entry_output.get().strip()
        if not output_dir or not os.path.isdir(output_dir):
            messagebox.showerror("错误", "请选择有效的输出文件夹路径")
            return

        success_count = 0
        fail_count = 0
        log_entries = []

        for f in selected:
            preview, err = process_subtitle(f, shift_sec, output_dir)
            if err:
                self.tree.set(f, "status", f"处理失败: {err}")
                fail_count += 1
                log_entries.append(f"{datetime.now()} 处理失败 {f} 错误: {err}\n")
            else:
                self.tree.set(f, "status", "处理成功")
                success_count += 1
                log_entries.append(f"{datetime.now()} 处理成功 {f} 偏移 {shift_sec} 秒\n")

        with open(self.log_path, 'a', encoding='utf-8') as logf:
            logf.writelines(log_entries)

        messagebox.showinfo("完成", f"处理完成！成功: {success_count}，失败: {fail_count}\n日志文件: {self.log_path}")

def process_subtitle_preview(file_path, shift_seconds):
    fmt = os.path.splitext(file_path)[-1].lower().lstrip('.')
    if fmt not in ['srt', 'vtt']:
        return None, "不支持的字幕格式"

    encoding = detect_encoding(file_path)

    with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
        lines = f.readlines()

    shift_ms = int(shift_seconds * 1000)
    preview_changes = []

    for line in lines:
        if '-->' in line:
            try:
                old_line = line.strip()
                new_line = shift_timestamp_line(line, shift_ms, fmt).strip()
                preview_changes.append((old_line, new_line))
            except Exception as e:
                continue

    return preview_changes, None

if __name__ == '__main__':
    root = tk.Tk()
    app = SubtitleShiftApp(root)
    root.mainloop()
