import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

matched_files = []

def browse_directory():
    path = filedialog.askdirectory()
    if path:
        entry_path.delete(0, tk.END)
        entry_path.insert(0, path)

def preview_files():
    prefix = entry_prefix.get().strip()
    suffix = entry_suffix.get().strip()
    path = entry_path.get().strip()

    if not os.path.isdir(path):
        messagebox.showerror("错误", "请选择有效的文件夹路径")
        return

    if not prefix:
        messagebox.showerror("错误", "请输入前缀")
        return

    tree.delete(*tree.get_children())
    matched_files.clear()

    count = 1
    found = False

    print(f"开始扫描目录：{path}")
    for fname in os.listdir(path):
        full_path = os.path.join(path, fname)
        print(f"检查文件：{fname}")
        if os.path.isfile(full_path) and fname.startswith(prefix):
            found = True
            name, ext = os.path.splitext(fname)
            new_name = f"{prefix}-{suffix}{count}{ext}" if suffix else f"{prefix}-{count}{ext}"
            matched_files.append((full_path, os.path.join(path, new_name)))
            tree.insert('', 'end', values=(fname, os.path.basename(new_name)))
            print(f"匹配成功：{fname} → {new_name}")
            count += 1

    if not found:
        messagebox.showinfo("提示", "未找到符合前缀的文件。请检查输入是否准确。")

def rename_files():
    if not matched_files:
        messagebox.showwarning("提示", "没有可处理的文件，请先点击预览。")
        return

    renamed = 0
    for old_path, new_path in matched_files:
        try:
            if old_path != new_path and not os.path.exists(new_path):
                os.rename(old_path, new_path)
                renamed += 1
        except Exception as e:
            print(f"重命名失败：{old_path} -> {new_path}, 错误: {e}")

    messagebox.showinfo("完成", f"重命名完成，共处理 {renamed} 个文件。")
    preview_files()


# GUI 界面
root = tk.Tk()
root.title("批量重命名工具 - 严格前缀匹配 + 后缀序号")

tk.Label(root, text="选择文件夹：").grid(row=0, column=0, sticky="e")
entry_path = tk.Entry(root, width=50)
entry_path.grid(row=0, column=1)
tk.Button(root, text="浏览", command=browse_directory).grid(row=0, column=2)

tk.Label(root, text="前缀（严格匹配）：").grid(row=1, column=0, sticky="e")
entry_prefix = tk.Entry(root)
entry_prefix.grid(row=1, column=1)

tk.Label(root, text="后缀（可选）：").grid(row=2, column=0, sticky="e")
entry_suffix = tk.Entry(root)
entry_suffix.grid(row=2, column=1)

tk.Button(root, text="预览", command=preview_files).grid(row=3, column=1, sticky="w", pady=5)
tk.Button(root, text="执行重命名", command=rename_files).grid(row=3, column=1, sticky="e", pady=5)

tree = ttk.Treeview(root, columns=('原文件名', '新文件名'), show='headings', height=10)
tree.heading('原文件名', text='原文件名')
tree.heading('新文件名', text='新文件名')
tree.grid(row=4, column=0, columnspan=3, padx=10, pady=10)

root.mainloop()
