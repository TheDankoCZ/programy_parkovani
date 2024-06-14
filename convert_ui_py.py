import os
import subprocess


def convert_ui_to_py(ui_file):
    py_file = ui_file.replace('.ui', '.py')
    command = f"pyuic5 -o {py_file} {ui_file}"
    subprocess.run(command, shell=True)


if __name__ == "__main__":
    ui_files = [file for file in os.listdir() if file.endswith('.ui')]
    for ui_file in ui_files:
        convert_ui_to_py(ui_file)
