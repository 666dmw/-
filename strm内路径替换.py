import os
import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import chardet

def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        raw = f.read(1000)
    result = chardet.detect(raw)
    return result['encoding'] or 'utf-8'

def regex_replace_in_strm(folder, regex_pattern, replacement, name_filter, log_file):
    modified_files = []
    preview_map = {}

    pattern = re.compile(regex_pattern)

    for root, _, files in os.walk(folder):
        for file in files:
            if file.lower().endswith(".strm") and name_filter in file:
                full_path = os.path.join(root, file)
                encoding = detect_encoding(full_path)
                with open(full_path, 'r', encoding=encoding) as f:
                    content = f.read()

                new_content, count = pattern.subn(replacement, content)
                if count > 0:
                    preview_map[full_path] = (content.strip(), new_content.strip())
                    modified_files.append(full_path)

    with open(log_file, 'w', encoding='utf-8') as log:
        for path in modified_files:
            log.write(path + '\n')
    return preview_map, modified_files

def apply_changes(preview_map, root_folder):
    for full_path, (_, new_content) in preview_map.items():
        encoding = detect_encoding(full_path)
        rel_path = os.path.relpath(full_path, root_folder)
        backup_path = os.path.join(root_folder, "bak", rel_path)
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        shutil.copy2(full_path, backup_path)
        with open(full_path, 'w', encoding=encoding) as f:
            f.write(new_content)

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

def run_gui():
    def select_folder():
        path = filedialog.askdirectory()
        if path:
            entry_path.delete(0, tk.END)
            entry_path.insert(0, path)

    def start_preview():
        folder = entry_path.get()
        regex = entry_old.get()
        repl = entry_new.get()
        keyword = entry_keyword.get()
        if not (folder and regex):
            messagebox.showerror("错误", "请输入文件夹路径和正则表达式。")
            return

        log_file = os.path.join(folder, "strm_regex_replace_log.txt")
        preview, modified = regex_replace_in_strm(folder, regex, repl, keyword, log_file)

        text_preview.delete("1.0", tk.END)
        if not preview:
            text_preview.insert(tk.END, "没有找到匹配的内容。\n")
        else:
            for path, (old, new) in preview.items():
                text_preview.insert(tk.END, f"文件: {path}\n")
                text_preview.insert(tk.END, f"原内容: {old}\n")
                text_preview.insert(tk.END, f"新内容: {new}\n\n")
        global preview_result, preview_root
        preview_result = preview
        preview_root = folder

    def confirm_replace():
        if not preview_result:
            messagebox.showwarning("提示", "请先预览，确认有文件需要替换。")
            return
        apply_changes(preview_result, preview_root)
        messagebox.showinfo("完成", f"已完成替换并备份，修改了 {len(preview_result)} 个文件。\n备份保存在：{preview_root}/bak/")

    def restore_backup():
        folder = entry_path.get()
        if not folder:
            messagebox.showerror("错误", "请先选择目录")
            return
        count = restore_from_backup(folder)
        messagebox.showinfo("还原完成", f"已还原 {count} 个文件。")

    window = tk.Tk()
    window.title("STRM 文件 替换 + 备份还原 工具")

    tk.Label(window, text="选择目录：").grid(row=0, column=0, sticky="e")
    entry_path = tk.Entry(window, width=60)
    entry_path.grid(row=0, column=1)
    tk.Button(window, text="浏览", command=select_folder).grid(row=0, column=2)

    tk.Label(window, text="正则表达式：").grid(row=1, column=0, sticky="e")
    entry_old = tk.Entry(window, width=60)
    entry_old.grid(row=1, column=1, columnspan=2)

    tk.Label(window, text="替换为：").grid(row=2, column=0, sticky="e")
    entry_new = tk.Entry(window, width=60)
    entry_new.grid(row=2, column=1, columnspan=2)

    tk.Label(window, text="仅包含关键词：").grid(row=3, column=0, sticky="e")
    entry_keyword = tk.Entry(window, width=60)
    entry_keyword.grid(row=3, column=1, columnspan=2)
    entry_keyword.insert(0, "")

    tk.Button(window, text="预览修改", command=start_preview, bg="lightblue").grid(row=4, column=1, pady=5)
    tk.Button(window, text="确认替换", command=confirm_replace, bg="lightgreen").grid(row=4, column=2, pady=5)
    tk.Button(window, text="还原备份", command=restore_backup, bg="orange").grid(row=4, column=0, pady=5)

    text_preview = scrolledtext.ScrolledText(window, width=100, height=25)
    text_preview.grid(row=5, column=0, columnspan=3, padx=10, pady=10)

    global preview_result, preview_root
    preview_result = {}
    preview_root = ""
    window.mainloop()

if __name__ == "__main__":
    run_gui()
