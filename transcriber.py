import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from faster_whisper import WhisperModel

# Setup model
model_size = "large-v3"
model = WhisperModel(model_size, device="cuda", compute_type="float16")

class TranscriberApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Transcriber")
        
        # Set the base width and height of the window
        self.root.geometry("600x400")  # Width x Height

        self.file_list = []
        self.transcribing = False
        self.current_file = None

        # UI Components
        self.label = tk.Label(root, text="No file selected")
        self.label.pack(pady=10)

        self.status_label = tk.Label(root, text="Status: Idle")
        self.status_label.pack(pady=10)

        self.select_button = tk.Button(root, text="Select Files", command=self.select_files)
        self.select_button.pack(pady=5)

        self.transcribe_button = tk.Button(root, text="Start Transcription", command=self.start_transcription)
        self.transcribe_button.pack(pady=5)

        self.cancel_button = tk.Button(root, text="Cancel", command=self.cancel_transcription)
        self.cancel_button.pack(pady=5)

        self.skip_button = tk.Button(root, text="Skip", command=self.skip_file)
        self.skip_button.pack(pady=5)

    def select_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Audio Files", "*.mp3 *.wav")])
        if files:
            self.file_list = list(files)
            self.label.config(text=f"{len(files)} files selected")
    
    def transcribe_file(self, filename):
        try:
            self.current_file = filename
            output_filename = f"transcripts/{os.path.basename(filename)}.txt"

            segments, info = model.transcribe(filename, beam_size=5)
            with open(output_filename, "w", encoding="utf-8") as file:
                for segment in segments:
                    file.write("[%.2fs -> %.2fs] %s\n" % (segment.start, segment.end, segment.text))
                    print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))
            print(f"Finished transcribing {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Error while transcribing {filename}: {e}")

    def transcribe_all(self):
        self.transcribing = True
        self.update_ui_state()
        self.status_label.config(text="Status: Transcribing")
        for idx, file in enumerate(self.file_list):
            if not self.transcribing:
                break
            self.transcribe_file(file)
        self.transcribing = False
        self.update_ui_state()
        self.status_label.config(text="Status: Idle")

    def start_transcription(self):
        if not self.file_list:
            messagebox.showwarning("Warning", "No files selected for transcription!")
            return
        if not os.path.exists("transcripts"):
            os.makedirs("transcripts")
        self.transcribing = True
        threading.Thread(target=self.transcribe_all).start()

    def cancel_transcription(self):
        self.transcribing = False
        self.label.config(text="Transcription canceled")
        self.status_label.config(text="Status: Canceled")
        self.update_ui_state()

    def skip_file(self):
        self.transcribing = True
        print(f"Skipping {self.current_file}")
        # The next file will be processed automatically

    def update_ui_state(self):
        state = tk.DISABLED if self.transcribing else tk.NORMAL
        self.select_button.config(state=state)
        self.transcribe_button.config(state=state)
        self.skip_button.config(state=state)

# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = TranscriberApp(root)
    root.mainloop()