// static/js/main.js
const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB
const CHUNK_SIZE = 1024 * 1024; // 1MB chunks

const STATUS = {
    UPLOADING: 'uploading',
    PROCESSING: 'processing',
    TRANSCRIBING: 'transcribing',
    COMPLETED: 'completed',
    ERROR: 'error'
};

const STATUS_MESSAGES = {
    [STATUS.UPLOADING]: 'Uploading file...',
    [STATUS.PROCESSING]: 'Processing audio...',
    [STATUS.TRANSCRIBING]: 'Converting speech to text...',
    [STATUS.COMPLETED]: 'Transcription completed!',
    [STATUS.ERROR]: 'Error occurred'
};

class FileUploader {
    constructor() {
        this.form = document.getElementById('upload-form');
        this.fileInput = document.getElementById('audio-file');
        this.progressBar = document.querySelector('.progress-bar');
        this.progressContainer = document.getElementById('progress-bar-container');
        this.statusMessage = document.getElementById('status-message');
        
        this.bindEvents();
        this.startTime = null;
        this.currentStatus = null;
        this.uploadComplete = false;
        this.uploadId = localStorage.getItem('currentUploadId');
        this.checkPendingUpload();
    }

    bindEvents() {
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        this.fileInput.addEventListener('change', () => this.validateFile());
    }

    validateFile() {
        const file = this.fileInput.files[0];
        if (!file) return;

        if (file.size > MAX_FILE_SIZE) {
            this.showError('File size exceeds 100MB limit');
            this.fileInput.value = '';
            return false;
        }

        const extension = file.name.split('.').pop().toLowerCase();
        if (!['mp3', 'wav', 'm4a', 'aac'].includes(extension)) {
            this.showError('Invalid file type');
            this.fileInput.value = '';
            return false;
        }

        return true;
    }

    async handleSubmit(e) {
        e.preventDefault();
        if (!this.validateFile()) return;

        const file = this.fileInput.files[0];
        this.showProgress();
        
        try {
            const uploadComplete = await this.uploadFile(file);
            if (uploadComplete) {
                this.startTime = Date.now();
                await this.monitorTranscription();
            } else {
                throw new Error('Upload did not complete successfully');
            }
        } catch (error) {
            this.showError(`Upload failed: ${error.message}`);
        }
    }

    async checkPendingUpload() {
        if (this.uploadId) {
            const response = await fetch(`/status/${this.uploadId}`);
            if (response.ok) {
                const status = await response.json();
                if (status.status !== 'completed') {
                    this.showProgress();
                    await this.monitorTranscription();
                }
            }
            localStorage.removeItem('currentUploadId');
        }
    }

    async uploadFile(file) {
        this.uploadId = crypto.randomUUID();
        localStorage.setItem('currentUploadId', this.uploadId);
        try {
            this.updateStatus(STATUS.UPLOADING);
            const chunks = Math.ceil(file.size / CHUNK_SIZE);
            let uploadedChunks = 0;

            for (let i = 0; i < chunks; i++) {
                const chunk = file.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE);
                const formData = new FormData();
                formData.append('file', chunk);
                formData.append('chunk', i);
                formData.append('total_chunks', chunks);
                formData.append('filename', file.name);

                const response = await fetch('/upload-chunk', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    throw new Error(`Upload failed: ${response.statusText}`);
                }

                uploadedChunks++;
                this.updateProgress((uploadedChunks / chunks) * 50);
                
                const result = await response.json();
                if (result.status === 'completed') {
                    this.startTime = Date.now();
                    // Immediately start monitoring
                    await this.monitorTranscription();
                    return;
                }
            }
        } catch (error) {
            this.updateStatus(STATUS.ERROR, error.message);
            throw error;
        }
    }

    async monitorTranscription() {
        return new Promise((resolve, reject) => {
            const eventSource = new EventSource('/progress');
            const timeout = setTimeout(() => {
                eventSource.close();
                reject(new Error('Operation timed out'));
            }, 300000);

            eventSource.onmessage = (event) => {
                const progress = JSON.parse(event.data);
                console.log('Progress update:', progress); // Debug logging

                switch (progress.status) {
                    case 'processing':
                        this.updateStatus(STATUS.PROCESSING);
                        this.updateProgress(50 + (progress.percent * 0.25));
                        break;
                    case 'transcribing':
                        this.updateStatus(STATUS.TRANSCRIBING);
                        this.updateProgress(75 + (progress.percent * 0.25));
                        break;
                    case 'completed':
                        clearTimeout(timeout);
                        eventSource.close();
                        this.updateProgress(100);
                        this.updateStatus(STATUS.COMPLETED);
                        resolve();
                        this.onComplete();
                        break;
                    case 'error':
                        clearTimeout(timeout);
                        eventSource.close();
                        reject(new Error(progress.message));
                        break;
                }
            };

            eventSource.onerror = () => {
                clearTimeout(timeout);
                eventSource.close();
                reject(new Error('Connection lost'));
            };
        });
    }

    getProgressForStatus(progress) {
        switch(progress.status) {
            case 'processing':
                return 50 + (progress.percent * 0.25);
            case 'transcribing':
                return 75 + (progress.percent * 0.25);
            case 'completed':
                return 100;
            default:
                return this.progressBar.getAttribute('aria-valuenow');
        }
    }

    updateProgress(percent) {
        this.progressBar.style.width = `${percent}%`;
        this.progressBar.setAttribute('aria-valuenow', percent);
    }

    updateStatus(status, additionalInfo = '') {
        const statusText = STATUS_MESSAGES[status] || status;
        let message = statusText;

        if (status === STATUS.TRANSCRIBING && this.startTime) {
            const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
            message += ` (${elapsed}s elapsed)`;
        }

        if (additionalInfo) {
            message += ` - ${additionalInfo}`;
        }

        this.statusMessage.textContent = message;
        this.updateStatusStyle(status);
    }

    updateStatusStyle(status) {
        this.statusMessage.classList.remove('alert-info', 'alert-success', 'alert-danger', 'alert-warning');
        
        switch(status) {
            case STATUS.UPLOADING:
            case STATUS.PROCESSING:
            case STATUS.TRANSCRIBING:
                this.statusMessage.classList.add('alert-info');
                break;
            case STATUS.COMPLETED:
                this.statusMessage.classList.add('alert-success');
                break;
            case STATUS.ERROR:
                this.statusMessage.classList.add('alert-danger');
                break;
            default:
                this.statusMessage.classList.add('alert-warning');
        }
    }

    showProgress() {
        this.progressContainer.classList.remove('d-none');
        this.statusMessage.classList.remove('d-none');
        this.statusMessage.classList.remove('alert-danger');
        this.statusMessage.classList.add('alert-info');
    }

    showError(message) {
        this.statusMessage.classList.remove('d-none');
        this.statusMessage.classList.remove('alert-info');
        this.statusMessage.classList.add('alert-danger');
        this.statusMessage.textContent = message;
    }

    onComplete() {
        this.updateStatus(STATUS.COMPLETED);
        this.progressBar.classList.remove('progress-bar-animated');
        setTimeout(() => {
            window.location.href = '/viewer';
        }, 1500);
    }
}

// Separate viewer page functionality
class TranscriptViewer {
    constructor() {
        this.transcriptList = document.getElementById('transcript-list');
        this.transcriptContent = document.getElementById('transcript-content');
        this.copyBtn = document.getElementById('copy-btn');
        this.bindEvents();
    }

    bindEvents() {
        this.transcriptList?.addEventListener('click', async (e) => {
            if (e.target.classList.contains('list-group-item-action')) {
                await this.loadTranscript(e.target.dataset.file);
            }
        });

        this.copyBtn?.addEventListener('click', () => this.copyContent());
    }

    async loadTranscript(filename) {
        try {
            const response = await fetch(`/transcripts/${filename}`);
            const content = await response.text();
            this.transcriptContent.textContent = content;
        } catch (error) {
            console.error('Failed to load transcript:', error);
        }
    }

    copyContent() {
        navigator.clipboard.writeText(this.transcriptContent.textContent);
        this.copyBtn.textContent = 'Copied!';
        setTimeout(() => {
            this.copyBtn.textContent = 'Copy to Clipboard';
        }, 2000);
    }
}

// Initialize based on page
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('upload-form')) {
        new FileUploader();
    } else if (document.getElementById('transcript-list')) {
        new TranscriptViewer();
    }
});