import os
import re
import json
import urllib.parse
import traceback
import tkinter as tk
from tkinter import filedialog, scrolledtext
from tkinterdnd2 import TkinterDnD, DND_FILES
from threading import Thread
from concurrent.futures import ThreadPoolExecutor, as_completed

CONFIG_FILE = 'config.json'
VIDEO_EXTS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.ts', '.rmvb']

def trim_path_by_keyword(path, keyword):
    """
    以 keyword 为开始标志，截取 path 中 keyword 及其之后的部分，
    返回以单斜杠开头的相对路径，不会多余双斜杠。
    """
    if not keyword:
        # 关键词为空时，原样返回，但确保以 / 开头且不重复 //
        p = path.replace('\\', '/')
        p = '/' + p.lstrip('/')
        while p.startswith('//'):
            p = p[1:]
        return p

    keyword = keyword.replace('\\', '/')
    path = path.replace('\\', '/')

    pos = path.find(keyword)
    if pos == -1:
        # 关键词没找到，则同空关键词处理
        p = '/' + path.lstrip('/')
        while p.startswith('//'):
            p = p[1:]
        return p

    # 找到关键词后，截取关键词开始位置到末尾
    sub = path[pos:]
    # 确保以单个 / 开头
    if not sub.startswith('/'):
        sub = '/' + sub
    while sub.startswith('//'):
        sub = sub[1:]
    return sub

class StrmGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("115 目录树转 STRM 工具")
        self.root.geometry("800x640")
        self.folder_choices = set()
        self.selected_folders = set()
        self.create_widgets()
        self.load_config()

    def create_widgets(self):
        frame = tk.LabelFrame(self.root, text="基本设置", padx=10, pady=10)
        frame.pack(padx=10, pady=10, fill='x')

        # 目录树文件路径
        tk.Label(frame, text="① 目录树文件路径：").grid(row=0, column=0, sticky='w')
        self.path_var = tk.StringVar()
        path_entry = tk.Entry(frame, textvariable=self.path_var, width=60)
        path_entry.grid(row=0, column=1)
        path_entry.drop_target_register(DND_FILES)
        path_entry.dnd_bind('<<Drop>>', self.on_drop_files)
        tk.Button(frame, text="浏览", command=self.browse_file).grid(row=0, column=2)

        # Alist 链接前缀
        tk.Label(frame, text="② Alist 链接前缀：").grid(row=1, column=0, sticky='w')
        self.prefix_var = tk.StringVar()
        tk.Entry(frame, textvariable=self.prefix_var, width=60).grid(row=1, column=1, columnspan=2, sticky='w')

        # STRM 输出目录
        tk.Label(frame, text="③ STRM 输出目录：").grid(row=2, column=0, sticky='w')
        self.output_var = tk.StringVar()
        tk.Entry(frame, textvariable=self.output_var, width=60).grid(row=2, column=1)
        tk.Button(frame, text="浏览", command=self.browse_output).grid(row=2, column=2)

        # 最小文件大小
        tk.Label(frame, text="④ 最小文件大小 (MB)：").grid(row=3, column=0, sticky='w')
        self.min_size_var = tk.IntVar(value=0)
        tk.Entry(frame, textvariable=self.min_size_var, width=10).grid(row=3, column=1, sticky='w')

        self.encode_var = tk.BooleanVar(value=True)
        tk.Checkbutton(frame, text="链接自动 URL 编码", variable=self.encode_var).grid(row=3, column=2, sticky='w')

        self.save_var = tk.BooleanVar(value=True)
        tk.Checkbutton(frame, text="保存设置", variable=self.save_var).grid(row=4, column=1, sticky='w')

        # 输出文件扩展名
        tk.Label(frame, text="⑤ 输出文件扩展名：").grid(row=5, column=0, sticky='w')
        self.ext_var = tk.StringVar(value=".strm")
        tk.Entry(frame, textvariable=self.ext_var, width=10).grid(row=5, column=1, sticky='w')

        # 开始标志关键词
        tk.Label(frame, text="⑥ 开始标志关键词 (可留空)：").grid(row=6, column=0, sticky='w')
        self.start_keyword_var = tk.StringVar()
        tk.Entry(frame, textvariable=self.start_keyword_var, width=30).grid(row=6, column=1, sticky='w')

        tk.Button(self.root, text="📂 载入并选择生成文件夹", command=self.load_and_select_folders).pack(pady=5)
        tk.Button(self.root, text="✨ 开始生成 STRM 文件", command=self.start_generation).pack(pady=5)

        # 日志输出
        tk.Label(self.root, text="日志输出：").pack(anchor='w', padx=10)
        self.log_text = scrolledtext.ScrolledText(self.root, width=95, height=18)
        self.log_text.pack(padx=10, pady=5)

        self.status_var = tk.StringVar(value="✅ 等待开始...")
        tk.Label(self.root, textvariable=self.status_var, anchor='w', fg='blue').pack(fill='x', padx=10, pady=5)

    def browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("文本文件", "*.txt")])
        if path:
            self.path_var.set(path)

    def browse_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_var.set(folder)

    def on_drop_files(self, event):
        files = self.root.tk.splitlist(event.data)
        valid_txt_files = [f for f in files if f.lower().endswith('.txt')]
        if valid_txt_files:
            self.path_var.set(valid_txt_files[0])
            self.log(f"[拖入] 已设置目录树文件: {valid_txt_files[0]}")

    def log(self, text):
        self.log_text.insert(tk.END, text + '\n')
        self.log_text.see(tk.END)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.path_var.set(config.get('path', ''))
                self.prefix_var.set(config.get('prefix', ''))
                self.output_var.set(config.get('output', ''))
                self.min_size_var.set(config.get('min_size', 0))
                self.ext_var.set(config.get('ext', '.strm'))
                self.start_keyword_var.set(config.get('start_keyword', ''))
            except Exception as e:
                self.log(f"[错误] 配置文件读取失败: {e}")

    def save_config(self):
        if self.save_var.get():
            config = {
                'path': self.path_var.get(),
                'prefix': self.prefix_var.get(),
                'output': self.output_var.get(),
                'min_size': self.min_size_var.get(),
                'ext': self.ext_var.get(),
                'start_keyword': self.start_keyword_var.get(),
            }
            try:
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
            except Exception as e:
                self.log(f"[错误] 保存配置失败: {e}")

    def read_text_file_with_fallback(self, path):
        for enc in ['utf-8', 'utf-16', 'utf-8-sig', 'gb18030']:
            try:
                with open(path, 'r', encoding=enc) as f:
                    return f.readlines()
            except UnicodeDecodeError:
                continue
        raise UnicodeDecodeError("read", b"", 0, 1, "文件编码错误，建议另存为 UTF-8")

    def parse_directory_tree(self, lines):
        paths = []
        stack = []
        processing = False
        start_keyword = self.start_keyword_var.get().strip()

        for line in lines:
            line = line.rstrip('\n\r')
            if not line.strip():
                continue
            if start_keyword and start_keyword in line:
                stack = []
                processing = True
                continue
            if not start_keyword:
                processing = True

            if not processing:
                continue

            match = re.match(r'^([| ]+)[|\\/\-]+(.*)', line)
            if match:
                prefix = match.group(1)
                name = match.group(2).strip()
                depth = prefix.count('|')

                while len(stack) > depth:
                    stack.pop()
                while len(stack) < depth:
                    stack.append("")

                if len(stack) == depth:
                    stack[-1] = name
                else:
                    stack.append(name)

                full_path = '/'.join(stack)
                if any(name.lower().endswith(ext) for ext in VIDEO_EXTS):
                    paths.append(full_path)
        return paths

    def load_and_select_folders(self):
        try:
            lines = self.read_text_file_with_fallback(self.path_var.get())
            media_paths = self.parse_directory_tree(lines)
            folder_set = sorted(set(os.path.dirname(p) for p in media_paths))
            self.folder_choices = set(folder_set)
            self.selected_folders = set(folder_set)

            win = tk.Toplevel(self.root)
            win.title("选择需要生成的文件夹")
            win.geometry("500x400")

            tk.Label(win, text="请选择需要生成的文件夹：").pack(anchor='w')

            frame = tk.Frame(win)
            frame.pack(fill='both', expand=True)
            canvas = tk.Canvas(frame)
            scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
            canvas.configure(yscrollcommand=scrollbar.set)

            var_map = {}

            def toggle_all():
                new_val = all(var.get() for var in var_map.values())
                for var in var_map.values():
                    var.set(not new_val)

            tk.Button(win, text="全选 / 反选", command=toggle_all).pack()

            for folder in folder_set:
                var = tk.BooleanVar(value=True)
                chk = tk.Checkbutton(scrollable_frame, text=folder, variable=var)
                chk.pack(anchor='w')
                var_map[folder] = var

            def on_confirm():
                self.selected_folders = {k for k,v in var_map.items() if v.get()}
                self.log(f"[选择] 共选中 {len(self.selected_folders)} 个文件夹")
                win.destroy()

            tk.Button(win, text="确定", command=on_confirm).pack(pady=5)
            scrollbar.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)

        except Exception as e:
            self.log(f"[错误] 加载目录树失败: {e}")
            self.log(traceback.format_exc())

    def start_generation(self):
        t = Thread(target=self.generate_strm)
        t.setDaemon(True)
        t.start()

    def generate_strm(self):
        self.status_var.set("🔄 处理中...")
        self.log("开始生成 STRM 文件...")
        try:
            input_path = self.path_var.get()
            prefix = self.prefix_var.get().rstrip('/')
            output_dir = self.output_var.get()
            min_size = self.min_size_var.get()
            ext = self.ext_var.get()
            start_keyword = self.start_keyword_var.get().strip()
            encode_url = self.encode_var.get()

            if not input_path or not os.path.exists(input_path):
                self.log("[错误] 目录树文件路径无效！")
                self.status_var.set("❌ 目录树文件路径无效！")
                return
            if not prefix:
                self.log("[错误] 请填写 Alist 链接前缀！")
                self.status_var.set("❌ 链接前缀为空！")
                return
            if not output_dir:
                self.log("[错误] 请选择 STRM 输出目录！")
                self.status_var.set("❌ STRM 输出目录为空！")
                return

            lines = self.read_text_file_with_fallback(input_path)
            media_paths = self.parse_directory_tree(lines)
            # 过滤选择的文件夹
            media_paths = [p for p in media_paths if os.path.dirname(p) in self.selected_folders]
            if not media_paths:
                self.log("[提示] 没有找到符合条件的媒体文件。")
                self.status_var.set("⚠️ 没有符合条件的文件。")
                return

            total_files = len(media_paths)
            self.log(f"[信息] 找到 {total_files} 个媒体文件，开始写入...")

            def write_strm(path):
                try:
                    base = os.path.basename(path)
                    name_without_ext = os.path.splitext(base)[0]
                    safe_name = re.sub(r'[\\/:*?"<>|]', '_', name_without_ext)
                    if not safe_name.strip():
                        return "[跳过] 空文件名", 0
                    file_name = safe_name + ext

                    # 处理路径，截取开始关键词后的路径，保证格式正常
                    trimmed_path = trim_path_by_keyword(path, start_keyword)
                    relative_dir = os.path.dirname(trimmed_path).lstrip('/\\')
                    target_dir = os.path.join(output_dir, relative_dir)
                    os.makedirs(target_dir, exist_ok=True)

                    url_path = '/'.join(urllib.parse.quote(p) for p in trimmed_path.split('/')) if encode_url else trimmed_path
                    full_url = f"{prefix}/{url_path}".replace('//', '/').replace(':/', '://')

                    output_path = os.path.join(target_dir, file_name)
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(full_url + '\n')
                    return f"[写入] {output_path} → {full_url}", 1
                except Exception as e:
                    return f"[失败] 写入 {path} 错误: {e}", 0

            count = 0
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(write_strm, p): p for p in media_paths}
                for future in as_completed(futures):
                    result, ret = future.result()
                    self.log(result)
                    if ret:
                        count += 1

            self.log(f"[完成] 共生成 {count} 个 STRM 文件。")
            self.status_var.set(f"✅ 完成，生成 {count} 个文件。")
            self.save_config()
        except Exception as e:
            self.log(f"[异常] 生成过程中出现错误: {e}")
            self.log(traceback.format_exc())
            self.status_var.set("❌ 生成失败！")

def main():
    root = TkinterDnD.Tk()
    app = StrmGeneratorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
