# transcriber.py
from faster_whisper import WhisperModel
import os
from pathlib import Path

class Transcriber:
    def __init__(self):
        self.model = None
        self.progress = {'status': 'idle', 'percent': 0}
        self.load_model()
        
    def load_model(self):
        try:
            self.model = WhisperModel("large-v3", device="cpu", compute_type="int8")
        except Exception as e:
            print(f"Error loading model: {e}")
            
    def transcribe_file(self, filepath):
        try:
            print(f"Starting transcription of {filepath}")  # Debug log
            self.progress = {'status': 'processing', 'percent': 0}
            print("Progress updated to processing")  # Debug log
            
            segments, info = self.model.transcribe(filepath)
            print("Initial transcription complete")  # Debug log
            
            if not segments:
                raise Exception("No segments were transcribed")
            
            self.progress = {'status': 'transcribing', 'percent': 0}
            print("Progress updated to transcribing")  # Debug log
            
            # Transcription stage
            output_path = Path('transcripts') / f"{Path(filepath).stem}.txt"
            with open(output_path, "w", encoding="utf-8") as f:
                for segment in segments:
                    f.write(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}\n")
                    self.progress['percent'] = int((segment.end / info.duration) * 100)
                    
            self.progress = {'status': 'completed', 'percent': 100}
            
            os.remove(filepath)
            
        except Exception as e:
            self.progress = {'status': 'error', 'message': str(e)}
            
    def get_progress(self):
        return self.progress