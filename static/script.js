// NinerMatch Upload Page JavaScript

function showUploadSection() {
    document.getElementById('uploadSection').style.display = 'block';
    document.getElementById('uploadSection').scrollIntoView({ behavior: 'smooth' });
}

document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    // Prevent double file picker popup by handling browse button click separately
    const browseBtn = document.getElementById('browseBtn');
    if (browseBtn) {
        browseBtn.addEventListener('click', function(event) {
            event.stopPropagation();
            fileInput.click();
        });
    }
    const uploadProgress = document.getElementById('uploadProgress');
    const errorMessage = document.getElementById('errorMessage');
    const progressFill = document.querySelector('.progress-fill');
    const progressText = document.querySelector('.progress-text');

    // Drag and drop functionality
    dropZone.addEventListener('dragover', handleDragOver);
    dropZone.addEventListener('dragleave', handleDragLeave);
    dropZone.addEventListener('drop', handleDrop);
    dropZone.addEventListener('click', () => fileInput.click());

    // File input change
    fileInput.addEventListener('change', handleFileSelect);

    function handleDragOver(e) {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    }

    function handleDragLeave(e) {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
    }

    function handleDrop(e) {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    }

    function handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            handleFile(file);
        }
    }

    function handleFile(file) {
        // Prevent double uploads
        if (dropZone.classList.contains('uploading')) {
            showError('Upload already in progress. Please wait...');
            return;
        }

        // Validate file
        if (!validateFile(file)) {
            return;
        }

        // Hide error messages
        hideError();

        // Mark as uploading to prevent double uploads
        dropZone.classList.add('uploading');

        // Show progress
        showProgress();

        // Upload file
        uploadFile(file);
    }

    function validateFile(file) {
        // Check file type
        if (file.type !== 'application/pdf') {
            showError('Please select a PDF file.');
            return false;
        }

        // Check file size (16MB limit)
        const maxSize = 16 * 1024 * 1024;
        if (file.size > maxSize) {
            showError('File size must be less than 16MB.');
            return false;
        }

        return true;
    }

    function uploadFile(file) {
        const formData = new FormData();
        formData.append('resume', file);

        // Simulate progress
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += Math.random() * 15;
            if (progress >= 90) {
                clearInterval(progressInterval);
                progress = 90;
            }
            updateProgress(progress, 'Processing your resume...');
        }, 200);

        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            clearInterval(progressInterval);
            updateProgress(100, 'Processing complete!');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Redirect to review page immediately - data is stored in Flask session
                window.location.href = '/review';
            } else {
                throw new Error(data.error || 'Failed to process resume');
            }
        })
        .catch(error => {
            clearInterval(progressInterval);
            resetUploadState();
            showError('Failed to process resume: ' + error.message);
            console.error('Upload error:', error);
        });
    }

    function resetUploadState() {
        dropZone.classList.remove('uploading');
        hideProgress();
    }

    function showProgress() {
        uploadProgress.style.display = 'block';
        dropZone.style.display = 'none';
    }

    function hideProgress() {
        uploadProgress.style.display = 'none';
        dropZone.style.display = 'block';
    }

    function updateProgress(percent, text) {
        progressFill.style.width = percent + '%';
        progressText.textContent = text;
    }

    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.style.display = 'block';
        hideProgress();
    }

    function hideError() {
        errorMessage.style.display = 'none';
    }

    // Add some visual feedback for the drop zone
    document.addEventListener('dragover', (e) => e.preventDefault());
    document.addEventListener('drop', (e) => e.preventDefault());

    // Parser services removed - using local parser only
});