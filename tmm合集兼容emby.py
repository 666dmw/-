from PyQt5 import QtWidgets, QtCore
import os
import shutil
import xml.etree.ElementTree as ET
import configparser

CONFIG_FILE = "config.ini"

class DragDropLineEdit(QtWidgets.QLineEdit):
    """
    支持拖放文件夹的 QLineEdit
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        # 判断拖入是否为文件夹，接受拖放
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if os.path.isdir(url.toLocalFile()):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        # 拖放时取第一个文件夹路径写入文本框
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                self.setText(path)
                break

class FolderRenamer(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("TMM合集文件夹重命名工具（输入输出目录均支持拖放）")
        self.setMinimumSize(700, 520)

        self.root_dir = None
        self.output_dir = None

        layout = QtWidgets.QVBoxLayout(self)

        # 根目录选择区（支持拖放）
        root_layout = QtWidgets.QHBoxLayout()
        self.root_dir_edit = DragDropLineEdit()
        self.root_dir_edit.setPlaceholderText("请选择或拖入 TMM 合集根目录")
        self.root_dir_edit.setReadOnly(False)
        self.root_dir_edit.textChanged.connect(self.on_root_dir_changed)
        self.root_btn = QtWidgets.QPushButton("选择根目录")
        self.root_btn.clicked.connect(self.select_root_directory)
        root_layout.addWidget(self.root_dir_edit)
        root_layout.addWidget(self.root_btn)
        layout.addLayout(root_layout)

        # 输出目录选择区（也支持拖放）
        output_layout = QtWidgets.QHBoxLayout()
        self.output_dir_edit = DragDropLineEdit()
        self.output_dir_edit.setPlaceholderText("请选择或拖入输出目录")
        self.output_dir_edit.setReadOnly(False)
        self.output_dir_edit.textChanged.connect(self.on_output_dir_changed)
        self.output_btn = QtWidgets.QPushButton("选择输出目录")
        self.output_btn.clicked.connect(self.select_output_directory)
        output_layout.addWidget(self.output_dir_edit)
        output_layout.addWidget(self.output_btn)
        layout.addLayout(output_layout)

        # 预览和执行按钮
        btn_layout = QtWidgets.QHBoxLayout()
        self.preview_btn = QtWidgets.QPushButton("生成重命名预览")
        self.preview_btn.clicked.connect(self.generate_preview)
        self.process_btn = QtWidgets.QPushButton("开始重命名文件夹")
        self.process_btn.clicked.connect(self.rename_folders)
        self.process_btn.setEnabled(False)
        btn_layout.addWidget(self.preview_btn)
        btn_layout.addWidget(self.process_btn)
        layout.addLayout(btn_layout)

        # 预览表格
        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["原文件夹名", "重命名后文件夹名"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        layout.addWidget(self.table)

        # 日志输出框
        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        self.preview_list = []

        self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE, encoding="utf-8")
            root = config.get("paths", "root_dir", fallback="")
            output = config.get("paths", "output_dir", fallback="")
            if root and os.path.isdir(root):
                self.root_dir = root
                self.root_dir_edit.setText(root)
            if output and os.path.isdir(output):
                self.output_dir = output
                self.output_dir_edit.setText(output)

    def save_config(self):
        config = configparser.ConfigParser()
        config["paths"] = {
            "root_dir": self.root_dir_edit.text(),
            "output_dir": self.output_dir_edit.text()
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            config.write(f)

    def on_root_dir_changed(self, text):
        self.root_dir = text
        self.save_config()

    def on_output_dir_changed(self, text):
        self.output_dir = text
        self.save_config()

    def select_root_directory(self):
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(self, "选择 TMM 合集根目录")
        if dir_path:
            self.root_dir = dir_path
            self.root_dir_edit.setText(dir_path)
            self.log.append(f"选择根目录: {dir_path}")
            self.save_config()

    def select_output_directory(self):
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.output_dir = dir_path
            self.output_dir_edit.setText(dir_path)
            self.log.append(f"选择输出目录: {dir_path}")
            self.save_config()

    def generate_preview(self):
        self.log.clear()
        self.table.setRowCount(0)
        self.preview_list.clear()

        if not self.root_dir_edit.text():
            self.log.append("❌ 请先选择或拖入 TMM 合集根目录")
            return

        if not self.output_dir_edit.text():
            self.log.append("❌ 请先选择或拖入输出目录")
            return

        root_dir = self.root_dir_edit.text()
        out_dir = self.output_dir_edit.text()

        count = 0
        for subdir, dirs, files in os.walk(root_dir):
            if 'collection.nfo' in files:
                try:
                    rel_path = os.path.relpath(subdir, root_dir)
                    old_folder_name = os.path.basename(rel_path)

                    tree = ET.parse(os.path.join(subdir, 'collection.nfo'))
                    root = tree.getroot()

                    title = root.findtext('title')
                    tmdbid = root.findtext('tmdbid')

                    if not tmdbid:
                        for uid in root.findall('uniqueid'):
                            if uid.attrib.get('type') == 'tmdb':
                                tmdbid = uid.text
                                break

                    if not tmdbid:
                        self.log.append(f"⚠️ 跳过 {title}，未找到 tmdb id")
                        continue

                    new_folder_name = f"{title}-tmdb-{tmdbid}"
                    new_full_path = os.path.join(out_dir, os.path.dirname(rel_path), new_folder_name)

                    self.preview_list.append((subdir, new_full_path))

                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(old_folder_name))
                    self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(new_folder_name))

                    count += 1
                except Exception as e:
                    self.log.append(f"❌ 解析失败: {subdir} -> {str(e)}")

        if count == 0:
            self.log.append("⚠️ 未找到任何有效合集或collection.nfo")
            self.process_btn.setEnabled(False)
        else:
            self.log.append(f"ℹ️ 生成预览成功，共 {count} 个合集")
            self.process_btn.setEnabled(True)

    def rename_folders(self):
        if not self.preview_list:
            self.log.append("❌ 请先生成重命名预览")
            return

        count = 0
        for src_folder, dst_folder in self.preview_list:
            try:
                os.makedirs(os.path.dirname(dst_folder), exist_ok=True)
                if not os.path.exists(dst_folder):
                    shutil.copytree(src_folder, dst_folder)
                    count += 1
                    old_name = os.path.basename(src_folder)
                    new_name = os.path.basename(dst_folder)
                    self.log.append(f"✅ 已重命名: {old_name} → {new_name}")
                else:
                    self.log.append(f"⚠️ 目标文件夹已存在，跳过: {dst_folder}")
            except Exception as e:
                self.log.append(f"❌ 重命名失败: {src_folder} -> {str(e)}")

        self.log.append(f"\n🎉 总共重命名合集文件夹：{count} 个")
        self.process_btn.setEnabled(False)

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = FolderRenamer()
    window.show()
    sys.exit(app.exec_())
