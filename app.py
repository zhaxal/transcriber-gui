# app.py
from flask import Flask, render_template, request, jsonify, Response, session
from werkzeug.utils import secure_filename
import os
from transcriber import Transcriber
from pathlib import Path
import json
import time
from threading import Thread
import uuid
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['TRANSCRIPT_FOLDER'] = 'transcripts'
app.config['MAX_CONTENT_LENGTH'] = 104857600  # 100MB limit

# Add new config for chunks
app.config['CHUNK_FOLDER'] = 'chunks'
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
app.config['SESSION_TYPE'] = os.getenv('FLASK_SESSION_TYPE')

# Ensure folders exist
Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)
Path(app.config['TRANSCRIPT_FOLDER']).mkdir(exist_ok=True)
Path(app.config['CHUNK_FOLDER']).mkdir(exist_ok=True)

transcriber = Transcriber()

ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'aac'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/viewer')
def viewer():
    transcripts = []
    transcript_dir = Path(app.config['TRANSCRIPT_FOLDER'])
    if transcript_dir.exists():
        transcripts = sorted(
            transcript_dir.glob("*.txt"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
    return render_template('viewer.html', transcripts=transcripts)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    transcriber.transcribe_file(filepath)
    return jsonify({'message': 'File uploaded successfully'})

def start_transcription(filepath):
    Thread(target=transcriber.transcribe_file, args=(str(filepath),), daemon=True).start()

@app.route('/upload-chunk', methods=['POST'])
def upload_chunk():
    session['upload_id'] = str(uuid.uuid4())
    session['filename'] = secure_filename(request.form['filename'])
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
        
    chunk = request.files['file']
    chunk_number = int(request.form['chunk'])
    total_chunks = int(request.form['total_chunks'])
    original_filename = request.form['filename']
    
    if not allowed_file(original_filename):
        return jsonify({'error': 'Invalid file type'}), 400
        
    # Create temp directory for chunks
    temp_dir = Path(app.config['CHUNK_FOLDER']) / secure_filename(original_filename)
    temp_dir.mkdir(exist_ok=True)
    
    # Save chunk
    chunk_path = temp_dir / f"chunk_{chunk_number}"
    chunk.save(chunk_path)
    
    # Check if all chunks received
    if chunk_number == total_chunks - 1:
        try:
            # Combine chunks
            final_path = Path(app.config['UPLOAD_FOLDER']) / secure_filename(original_filename)
            with open(final_path, 'wb') as outfile:
                for i in range(total_chunks):
                    chunk_file = temp_dir / f"chunk_{i}"
                    outfile.write(chunk_file.read_bytes())
            
            # Cleanup chunks
            import shutil
            shutil.rmtree(temp_dir)
            
            # Start transcription asynchronously
            start_transcription(final_path)
            return jsonify({
                'status': 'completed',
                'message': 'Starting transcription'
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            
    return jsonify({'status': 'chunk_received'})

@app.route('/progress')
def progress():
    def generate():
        last_status = None
        attempts = 0
        max_attempts = 300  # 5 minutes timeout
        
        while attempts < max_attempts:
            progress = transcriber.get_progress()
            current_status = progress['status']
            
            # Only yield if status changed or is error/completed
            if (current_status != last_status or 
                current_status in ['error', 'completed']):
                yield f"data: {json.dumps(progress)}\n\n"
                
            if current_status == 'error':
                break
            if current_status == 'completed':
                break
                
            last_status = current_status
            attempts += 1
            time.sleep(1)
            
        if attempts >= max_attempts:
            yield f"data: {json.dumps({'status': 'error', 'message': 'Timeout'})}\n\n"
            
    return Response(generate(), mimetype='text/event-stream')

@app.route('/transcripts/<filename>')
def get_transcript(filename):
    filepath = Path(app.config['TRANSCRIPT_FOLDER']) / filename
    if filepath.exists():
        return filepath.read_text()
    return 'Transcript not found', 404

@app.route('/status/<upload_id>')
def get_upload_status(upload_id):
    if session.get('upload_id') == upload_id:
        return jsonify({
            'filename': session.get('filename'),
            'progress': transcriber.get_progress()
        })
    return jsonify({'status': 'not_found'}), 404

if __name__ == '__main__':
    app.run(debug=True)