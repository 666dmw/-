import os
import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import chardet

# 检测文件编码，避免编码错误
def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        raw = f.read(1000)
    result = chardet.detect(raw)
    return result['encoding'] or 'utf-8'

# 自动对正则表达式中的特殊字符进行转义
def escape_regex_special_chars(s):
    return re.escape(s)

# 在 .strm 文件中替换匹配内容，并预览修改结果
def regex_replace_in_strm(folder, target_text, replacement, name_filter, log_file):
    modified_files = []  # 保存被修改的文件路径
    preview_map = {}     # 保存每个文件的修改前后内容

    # 自动转义输入的匹配文本，防止正则报错
    pattern = re.compile(escape_regex_special_chars(target_text))

    for root, _, files in os.walk(folder):
        for file in files:
            # 只处理 .strm 文件，且文件名中包含指定关键词（如果有）
            if file.lower().endswith(".strm") and (not name_filter or name_filter in file):
                full_path = os.path.join(root, file)
                encoding = detect_encoding(full_path)
                with open(full_path, 'r', encoding=encoding) as f:
                    content = f.read()

                # 替换匹配的文本
                new_content, count = pattern.subn(replacement, content)
                if count > 0:
                    preview_map[full_path] = (content.strip(), new_content.strip())
                    modified_files.append(full_path)

    # 记录被修改的文件到日志
    with open(log_file, 'w', encoding='utf-8') as log:
        for path in modified_files:
            log.write(path + '\n')
    return preview_map, modified_files

# 应用修改并备份原始文件
def apply_changes(preview_map, root_folder):
    for full_path, (_, new_content) in preview_map.items():
        encoding = detect_encoding(full_path)
        rel_path = os.path.relpath(full_path, root_folder)
        backup_path = os.path.join(root_folder, "bak", rel_path)
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        shutil.copy2(full_path, backup_path)  # 备份原文件
        with open(full_path, 'w', encoding=encoding) as f:
            f.write(new_content)

# 从备份中恢复所有 .strm 文件
def restore_from_backup(folder):
    bak_folder = os.path.join(folder, "bak")
    if not os.path.exists(bak_folder):
        messagebox.showwarning("没有找到备份", f"未找到备份目录：{bak_folder}")
        return 0

    restored = 0
    for root, _, files in os.walk(bak_folder):
        for file in files:
            if file.lower().endswith(".strm"):
                rel_path = os.path.relpath(os.path.join(root, file), bak_folder)
                target_path = os.path.join(folder, rel_path)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy2(os.path.join(root, file), target_path)
                restored += 1
    return restored

# 图形界面主程序
def run_gui():
    # 选择文件夹
    def select_folder():
        path = filedialog.askdirectory()
        if path:
            entry_path.delete(0, tk.END)
            entry_path.insert(0, path)

    # 点击“预览修改”后执行的操作
    def start_preview():
        folder = entry_path.get()
        target_text = entry_old.get()
        repl = entry_new.get()
        keyword = entry_keyword.get()
        if not (folder and target_text):
            messagebox.showerror("错误", "请输入文件夹路径和目标文本。")
            return

        log_file = os.path.join(folder, "strm_regex_replace_log.txt")
        preview, modified = regex_replace_in_strm(folder, target_text, repl, keyword, log_file)

        text_preview.delete("1.0", tk.END)
        if not preview:
            text_preview.insert(tk.END, "没有找到匹配的内容。\n")
        else:
            for path, (old, new) in preview.items():
                text_preview.insert(tk.END, f"文件: {path}\n")
                text_preview.insert(tk.END, f"原内容: {old}\n")
                text_preview.insert(tk.END, f"新内容: {new}\n\n")
        # 保存全局变量用于确认替换
        global preview_result, preview_root
        preview_result = preview
        preview_root = folder

    # 确认替换按钮点击后执行的操作
    def confirm_replace():
        if not preview_result:
            messagebox.showwarning("提示", "请先预览，确认有文件需要替换。")
            return
        apply_changes(preview_result, preview_root)
        messagebox.showinfo("完成", f"已完成替换并备份，修改了 {len(preview_result)} 个文件。\n备份保存在：{preview_root}/bak/")

    # 还原备份文件
    def restore_backup():
        folder = entry_path.get()
        if not folder:
            messagebox.showerror("错误", "请先选择目录")
            return
        count = restore_from_backup(folder)
        messagebox.showinfo("还原完成", f"已还原 {count} 个文件。")

    # 构建图形界面布局
    window = tk.Tk()
    window.title("STRM 文件 批量替换工具（带备份还原）")

    tk.Label(window, text="选择目录：").grid(row=0, column=0, sticky="e")
    entry_path = tk.Entry(window, width=60)
    entry_path.grid(row=0, column=1)
    tk.Button(window, text="浏览", command=select_folder).grid(row=0, column=2)

    tk.Label(window, text="匹配文本（自动转义）：").grid(row=1, column=0, sticky="e")
    entry_old = tk.Entry(window, width=60)
    entry_old.grid(row=1, column=1, columnspan=2)

    tk.Label(window, text="替换为：").grid(row=2, column=0, sticky="e")
    entry_new = tk.Entry(window, width=60)
    entry_new.grid(row=2, column=1, columnspan=2)

    tk.Label(window, text="仅包含关键词（可选）：").grid(row=3, column=0, sticky="e")
    entry_keyword = tk.Entry(window, width=60)
    entry_keyword.grid(row=3, column=1, columnspan=2)

    # 三个主操作按钮
    tk.Button(window, text="预览修改", command=start_preview, bg="lightblue").grid(row=4, column=1, pady=5)
    tk.Button(window, text="确认替换", command=confirm_replace, bg="lightgreen").grid(row=4, column=2, pady=5)
    tk.Button(window, text="还原备份", command=restore_backup, bg="orange").grid(row=4, column=0, pady=5)

    # 显示预览结果
    text_preview = scrolledtext.ScrolledText(window, width=100, height=25)
    text_preview.grid(row=5, column=0, columnspan=3, padx=10, pady=10)

    # 初始化全局变量用于替换和还原
    global preview_result, preview_root
    preview_result = {}
    preview_root = ""
    window.mainloop()

# 主程序入口
if __name__ == "__main__":
    run_gui()
