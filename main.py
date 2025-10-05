import subprocess
import sys
import os
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox

SCRIPT_PATH = "question_answer.py"  # change to your script, or use "-m your.package.module"

def set_running(state: bool):
    run_button.config(state=("disabled" if state else "normal"))
    input_entry.config(state=("disabled" if state else "normal"))

def append_output(text: str):
    output_box.insert(tk.END, text)
    output_box.see(tk.END)

def run_script():
    # Read input from the on-screen entry
    user_input = input_var.get().strip()
    if not user_input:
        messagebox.showinfo("Missing input", "Please enter a value before running.")
        return

    def worker():
        try:
            # Build command using same interpreter/venv as this GUI
            cmd = [sys.executable, "-u", SCRIPT_PATH, user_input]
            # If calling a module instead of a file, use:
            # cmd = [sys.executable, "-u", "-m", "your.package.module", user_input]
            root.after(0, append_output, f"=== {user_input} ===\n<< Processing query... >>\n")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=os.environ,
                cwd=os.getcwd(),
            )
            out = (result.stdout or "").rstrip()
            err = (result.stderr or "").rstrip()

            # GUI
            root.after(0, append_output, (out or "(no stdout)") + "\n")
            if err:
                root.after(0, append_output, "=== Errors ===\n")
                root.after(0, append_output, err + "\n")
            root.after(0, append_output, "=====================\n\n")

        except Exception as e:
            root.after(0, append_output, f"Error running script: {e}\n")
        finally:
            root.after(0, set_running, False)

    set_running(True)
    threading.Thread(target=worker, daemon=True).start()

def on_enter(event):
    run_script()

def exit_app():
    root.destroy()

# --- GUI setup ---
root = tk.Tk()
root.title("Redesign Health Knowledge Engine")
root.geometry("760x480")

top = tk.Frame(root)
top.pack(fill=tk.X, padx=10, pady=10)

tk.Label(top, text="What Is Your Quest?").pack(side=tk.LEFT)
input_var = tk.StringVar()
input_entry = tk.Entry(top, textvariable=input_var, width=40)
input_entry.pack(side=tk.LEFT, padx=8)
input_entry.bind("<Return>", on_enter)

run_button = tk.Button(top, text="Submit Question", command=run_script)
run_button.pack(side=tk.LEFT, padx=6)

exit_button = tk.Button(top, text="Exit", command=exit_app)
exit_button.pack(side=tk.LEFT, padx=6)

output_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=20)
output_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

# Focus the input on launch
input_entry.focus()

root.mainloop()
