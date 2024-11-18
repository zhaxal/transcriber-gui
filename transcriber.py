import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from faster_whisper import WhisperModel

class TranscriberApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Transcriber")
        self.root.geometry("800x600")
        
        # Theme setup
        self.style = ttk.Style()
        self.style.theme_use('default')
        
        # Variables
        self.file_list = []
        self.transcribing = False
        self.current_file = None
        self.queue_position = 0
        
        self.setup_ui()
        self.load_model()
        self.bind_shortcuts()
        
    def load_model(self):
        try:
            self.log_message("Loading model...")
            self.model = WhisperModel("large-v3", device="cpu", compute_type="int8")
            self.log_message("Model loaded successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load model: {e}")
            self.log_message(f"Error loading model: {e}")
            
    def setup_ui(self):
        # Main containers
        self.top_frame = ttk.Frame(self.root)
        self.middle_frame = ttk.Frame(self.root)
        self.bottom_frame = ttk.Frame(self.root)
        
        for frame in (self.top_frame, self.middle_frame, self.bottom_frame):
            frame.pack(fill=tk.X, padx=10, pady=5)
            
        # File queue display
        self.queue_frame = ttk.LabelFrame(self.middle_frame, text="File Queue")
        self.queue_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.queue_list = tk.Listbox(self.queue_frame, height=10)
        self.queue_list.pack(fill=tk.BOTH, expand=True)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(self.middle_frame, 
        variable=self.progress_var,
        maximum=100)
        self.progress.pack(fill=tk.X, pady=5)
        
        # Log display
        self.log_frame = ttk.LabelFrame(self.bottom_frame, text="Log")
        self.log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = tk.Text(self.log_frame, height=5, width=50, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.log_frame, orient="vertical", 
                                 command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        # Current file label remains
        self.current_file_label = ttk.Label(self.bottom_frame, 
                                          text="Current file: None")
        self.current_file_label.pack(side=tk.RIGHT, pady=5)
        
        # Buttons
        self.button_frame = ttk.Frame(self.top_frame)
        self.button_frame.pack(fill=tk.X)
        
        self.select_button = ttk.Button(self.button_frame, 
                                      text="Select Files (⌘O)",
                                      command=self.select_files)
        self.transcribe_button = ttk.Button(self.button_frame,
                                          text="Start (⌘R)",
                                          command=self.start_transcription)
        self.cancel_button = ttk.Button(self.button_frame,
                                      text="Cancel (⌘C)",
                                      command=self.cancel_transcription)
        self.skip_button = ttk.Button(self.button_frame,
                                    text="Skip (⌘S)",
                                    command=self.skip_file)
        
        for btn in (self.select_button, self.transcribe_button,
                   self.cancel_button, self.skip_button):
            btn.pack(side=tk.LEFT, padx=5)
            
    def bind_shortcuts(self):
        self.root.bind('<Command-o>', lambda e: self.select_files())
        self.root.bind('<Command-r>', lambda e: self.start_transcription())
        self.root.bind('<Command-c>', lambda e: self.cancel_transcription())
        self.root.bind('<Command-s>', lambda e: self.skip_file())
        
    def update_queue_display(self):
        self.queue_list.delete(0, tk.END)
        for idx, file in enumerate(self.file_list):
            status = "🔄 " if idx == self.queue_position else "⏳ "
            self.queue_list.insert(tk.END, f"{status}{os.path.basename(file)}")
            
    def transcribe_file(self, filename):
        try:
            self.current_file = filename
            basename = os.path.basename(filename)
            self.current_file_label.config(text=f"Current file: {basename}")
            self.log_message(f"Transcribing {basename}...")
            
            segments, info = self.model.transcribe(filename, beam_size=5)
            
            output_path = os.path.join("transcripts", f"{basename}.txt")
            with open(output_path, "w", encoding="utf-8") as file:
                for segment in segments:
                    file.write(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}\n")
            
            self.log_message(f"Completed transcription of {basename}")
            self.queue_position += 1
            self.progress_var.set((self.queue_position / len(self.file_list)) * 100)
            self.update_queue_display()
            
        except Exception as e:
            error_msg = f"Error transcribing {basename}: {e}"
            messagebox.showerror("Error", error_msg)
            self.log_message(error_msg)
            
    def select_files(self):
        files = filedialog.askopenfilenames(
            filetypes=[("Audio Files", "*.mp3 *.wav *.m4a *.aac")]
        )
        if files:
            self.file_list = list(files)
            self.queue_position = 0
            self.progress_var.set(0)
            self.update_queue_display()
            
    def update_ui_state(self):
        state = "disabled" if self.transcribing else "normal"
        self.select_button.config(state=state)
        self.transcribe_button.config(state=state)
        
        # Skip button enabled only during transcription
        self.skip_button.config(state="normal" if self.transcribing else "disabled")
        self.cancel_button.config(state="normal" if self.transcribing else "disabled")

    def start_transcription(self):
        if not self.file_list:
            messagebox.showwarning("Warning", "No files selected")
            return
            
        if self.transcribing:
            return
            
        # Create transcripts directory if it doesn't exist
        os.makedirs("transcripts", exist_ok=True)
        
        self.transcribing = True
        self.update_ui_state()
        self.log_message("Starting transcription...")
        
        # Start transcription in a separate thread
        def transcribe_queue():
            while self.queue_position < len(self.file_list) and self.transcribing:
                self.transcribe_file(self.file_list[self.queue_position])
            
            self.transcribing = False
            self.current_file = None
            self.current_file_label.config(text="Current file: None")
            self.log_message("Transcription completed")
            self.update_ui_state()
        
        thread = threading.Thread(target=transcribe_queue)
        thread.daemon = True
        thread.start()

    def cancel_transcription(self):
        if self.transcribing:
            self.transcribing = False
            self.log_message("Transcription cancelled")
            self.queue_position = 0
            self.progress_var.set(0)
            self.update_queue_display()
            self.update_ui_state()

    def skip_file(self):
        if self.transcribing and self.current_file:
            self.queue_position += 1
            self.progress_var.set((self.queue_position / len(self.file_list)) * 100)
            self.update_queue_display()

    def log_message(self, message):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)  # Auto-scroll to bottom

if __name__ == "__main__":
    root = tk.Tk()
    app = TranscriberApp(root)
    root.mainloop()