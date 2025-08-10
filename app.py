from flask import Flask, request, redirect, send_from_directory, render_template_string, jsonify
from werkzeug.utils import safe_join
import subprocess
import os
import shlex
import uuid
import threading
import queue
import time
import json
from datetime import datetime, timedelta


app = Flask(__name__)

import os
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Global variables for queue and worker
download_queue = queue.Queue()
download_status = {}  # {task_id: {"status": "pending/downloading/completed/failed", "progress": 0, "filename": "", "error": "", "title": ""}}

# Download formats
FORMATS = {
    "mp4_hd": {
        "name": "MP4 HD (1080p/720p)",
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "ext": "mp4"
    },
    "mp4_sd": {
        "name": "MP4 SD (480p/360p)",
        "format": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best",
        "ext": "mp4"
    },
    "audio": {
        "name": "Audio Only (MP3)",
        "format": "bestaudio[ext=m4a]/bestaudio",
        "ext": "mp3"
    },
    "mp4_best": {
        "name": "Best Quality MP4",
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "ext": "mp4"
    }
}

INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <!-- Primary Meta Tags -->
    <title>Ad-free YT Download - Download YouTube Videos Without Ads</title>
    <meta name="title" content="Ad-free YT Download - Download YouTube Videos Without Ads">
    <meta name="description" content="Download YouTube videos in HD, MP4, MP3 formats without ads. Fast, free, and easy-to-use YouTube downloader. No registration required.">
    <meta name="keywords" content="youtube downloader, download youtube videos, youtube to mp4, youtube to mp3, ad-free youtube, free youtube downloader, HD video download">
    <meta name="author" content="emeenx">
    <meta name="robots" content="index, follow">
    
    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="{{ request.url }}">
    <meta property="og:title" content="Ad-free YT Download - Download YouTube Videos Without Ads">
    <meta property="og:description" content="Download YouTube videos in HD, MP4, MP3 formats without ads. Fast, free, and easy-to-use YouTube downloader.">
    <meta property="og:image" content="{{ request.url_root }}static/og-image.jpg">
    
    <!-- Twitter -->
    <meta property="twitter:card" content="summary_large_image">
    <meta property="twitter:url" content="{{ request.url }}">
    <meta property="twitter:title" content="Ad-free YT Download - Download YouTube Videos Without Ads">
    <meta property="twitter:description" content="Download YouTube videos in HD, MP4, MP3 formats without ads. Fast, free, and easy-to-use YouTube downloader.">
    <meta property="twitter:image" content="{{ request.url_root }}static/og-image.jpg">
    
    <!-- Canonical URL -->
    <link rel="canonical" href="{{ request.url }}">
    
    <!-- Favicon -->
    <link rel="icon" type="image/x-icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📺</text></svg>">
    
    <!-- Structured Data -->
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "WebApplication",
      "name": "Ad-free YT Download",
      "url": "{{ request.url }}",
      "description": "Download YouTube videos in HD, MP4, MP3 formats without ads. Fast, free, and easy-to-use YouTube downloader.",
      "applicationCategory": "MultimediaApplication",
      "operatingSystem": "Any",
      "offers": {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "USD"
      },
      "creator": {
        "@type": "Person",
        "name": "emeenx",
        "url": "https://linktr.ee/emeenx"
      }
    }
    </script>
    
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
</head>
<body class="bg-gradient-to-br from-blue-50 to-indigo-100 min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <!-- Header -->
        <div class="text-center mb-8">
            <h1 class="text-4xl font-bold text-gray-800 mb-2">
                <i class="fab fa-youtube text-red-500"></i>
                Ad-free YT Download
            </h1>
            <p class="text-gray-600">Free YouTube downloader - Download videos without ads, in HD MP4 and MP3 formats</p>
            
            <!-- SEO Content Section -->
            <div class="mt-6 max-w-3xl mx-auto text-center">
                <p class="text-sm text-gray-500 leading-relaxed">
                    Convert and download YouTube videos instantly. Supports HD quality, multiple formats including MP4 and MP3. 
                    No ads, no registration required. Fast, secure, and completely free YouTube video downloader.
                </p>
            </div>
        </div>

        <!-- Main Content -->
        
        <!-- Main Download Section -->
        <section class="max-w-2xl mx-auto bg-white rounded-lg shadow-lg p-6 mb-8" aria-label="YouTube Video Download Form">
            <div class="mb-6">
                <h2 class="text-xl font-semibold">Download YouTube Video</h2>
                <p class="text-sm text-gray-600 mt-1">Paste any YouTube URL to download in your preferred format</p>
            </div>
            
            <form id="downloadForm" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">YouTube URL</label>
                    <input type="url" name="url" id="urlInput" placeholder="https://youtu.be/o8IE_AK-WDw?si=..." required
                           class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent">
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Format</label>
                    <select name="format" id="formatSelect" 
                            class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent">
                        {% for key, format in formats.items() %}
                        <option value="{{ key }}">{{ format.name }}</option>
                        {% endfor %}
                    </select>
                </div>
                
                <button type="submit" id="downloadBtn" 
                        class="w-full bg-gradient-to-r from-blue-500 to-indigo-600 text-white py-3 rounded-lg hover:from-blue-600 hover:to-indigo-700 transition duration-200 font-medium">
                    <i class="fas fa-download mr-2"></i>Start Download
                </button>
</form>
        </section>

        <!-- Download Status -->
        <section id="downloadStatus" class="max-w-2xl mx-auto bg-white rounded-lg shadow-lg p-6 hidden" aria-label="Download Progress">
            <h3 class="text-lg font-semibold mb-4">Download Progress</h3>
            <div id="downloadList" class="space-y-3"></div>
        </section>

        <!-- Recent Downloads -->
        <section class="max-w-4xl mx-auto bg-white rounded-lg shadow-lg p-6" aria-label="Recent Downloads">
            <h3 class="text-lg font-semibold mb-4">Your Recent Downloads</h3>
            <div id="recentDownloads" class="space-y-3">
                {% if recent_files %}
                {% for file in recent_files %}
                <div class="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:bg-gray-100 transition duration-200">
                    <div class="flex items-center justify-between">
                        <!-- File Info -->
                        <div class="flex-1 min-w-0 mr-4">
                            <div class="flex items-center mb-2">
                                <i class="fas fa-file-video text-blue-500 mr-2" style="{% if file.name.endswith('.mp3') %}display:none;{% endif %}"></i>
                                <i class="fas fa-file-audio text-green-500 mr-2" style="{% if not file.name.endswith('.mp3') %}display:none;{% endif %}"></i>
                                <h4 class="font-medium text-gray-900 truncate">{{ file.display_name }}</h4>
                            </div>
                            <div class="flex items-center space-x-4 text-sm text-gray-500">
                                <span class="flex items-center">
                                    <i class="fas fa-clock mr-1"></i>
                                    {{ file.date }}
                                </span>
                                <span class="flex items-center">
                                    <i class="fas fa-hdd mr-1"></i>
                                    {{ file.size_formatted }}
                                </span>
                            </div>
                        </div>
                        
                        <!-- Action Buttons -->
                        <div class="flex items-center space-x-2">
                            <!-- Copy Link Button -->
                            <button onclick="copyToClipboard('{{ request.url_root }}file/{{ file.name }}', this)" 
                                    class="bg-blue-500 text-white px-3 py-2 rounded-lg hover:bg-blue-600 transition duration-200 text-sm">
                                <i class="fas fa-copy mr-1"></i>Copy Link
                            </button>
                            
                            <!-- Download Button -->
                            <a href="{{ file.download_url }}" 
                               class="bg-green-500 text-white px-3 py-2 rounded-lg hover:bg-green-600 transition duration-200 text-sm">
                                <i class="fas fa-download mr-1"></i>Download
                            </a>
                        </div>
                    </div>
                </div>
                {% endfor %}
                {% else %}
                <div class="text-center py-8 text-gray-500">
                    <i class="fas fa-folder-open text-4xl mb-4"></i>
                    <p>No downloads yet. Start by downloading ad-free videos!</p>
                </div>
                {% endif %}
            </div>
        </section>
        
        <!-- SEO Footer Content -->
        <footer class="max-w-4xl mx-auto mt-12 bg-white rounded-lg shadow-lg p-6">
            <div class="grid md:grid-cols-2 gap-6">
                <div>
                    <h4 class="font-semibold text-gray-800 mb-3">About Ad-free YT Download</h4>
                    <p class="text-sm text-gray-600 leading-relaxed">
                        Our YouTube video downloader allows you to save YouTube videos directly to your device. 
                        Download videos in high quality MP4 format or extract audio as MP3. 
                        No registration, no ads, completely free.
                    </p>
                </div>
                <div>
                    <h4 class="font-semibold text-gray-800 mb-3">Supported Formats</h4>
                    <ul class="text-sm text-gray-600 space-y-1">
                        <li>• MP4 HD (1080p, 720p) - High quality video downloads</li>
                        <li>• MP4 SD (480p, 360p) - Smaller file sizes</li>
                        <li>• MP3 Audio - Extract audio from any YouTube video</li>
                        <li>• Best Quality - Automatically selects highest available quality</li>
                    </ul>
                </div>
            </div>
            <div class="mt-6 pt-6 border-t border-gray-200 text-center">
                <p class="text-xs text-gray-500">
                    Free YouTube downloader tool. Download responsibly and respect copyright laws.
                </p>
            </div>
        </footer>
    </div>

    <!-- Toast Container -->
    <div id="toastContainer" class="fixed top-4 right-4 z-50 space-y-2"></div>

    <!-- Built by Credit -->
    <div class="fixed bottom-4 right-4 z-40">
        <a href="https://linktr.ee/emeenx" target="_blank" rel="noopener noreferrer" 
           class="bg-white shadow-lg rounded-lg px-4 py-2 text-sm text-gray-600 hover:text-gray-800 hover:shadow-xl transition-all duration-200 border border-gray-200 flex items-center space-x-2">
            <i class="fas fa-code text-blue-500"></i>
            <span>Built by <strong class="text-gray-800">emeenx</strong></span>
        </a>
    </div>

    <script>
        let downloadTasks = {};

        // Copy to clipboard function
        async function copyToClipboard(text, button) {
            try {
                await navigator.clipboard.writeText(text);
                
                // Update button temporarily
                const originalHTML = button.innerHTML;
                button.innerHTML = '<i class="fas fa-check mr-1"></i>Copied!';
                button.classList.remove('bg-blue-500', 'hover:bg-blue-600');
                button.classList.add('bg-green-500', 'hover:bg-green-600');
                
                // Show success toast
                showToast('Link copied to clipboard!', 'success');
                
                // Reset button after 2 seconds
                setTimeout(() => {
                    button.innerHTML = originalHTML;
                    button.classList.remove('bg-green-500', 'hover:bg-green-600');
                    button.classList.add('bg-blue-500', 'hover:bg-blue-600');
                }, 2000);
                
            } catch (err) {
                // Fallback for older browsers
                const textArea = document.createElement('textarea');
                textArea.value = text;
                document.body.appendChild(textArea);
                textArea.select();
                try {
                    document.execCommand('copy');
                    showToast('Link copied to clipboard!', 'success');
                    
                    // Update button temporarily
                    const originalHTML = button.innerHTML;
                    button.innerHTML = '<i class="fas fa-check mr-1"></i>Copied!';
                    button.classList.remove('bg-blue-500', 'hover:bg-blue-600');
                    button.classList.add('bg-green-500', 'hover:bg-green-600');
                    
                    setTimeout(() => {
                        button.innerHTML = originalHTML;
                        button.classList.remove('bg-green-500', 'hover:bg-green-600');
                        button.classList.add('bg-blue-500', 'hover:bg-blue-600');
                    }, 2000);
                } catch (err) {
                    showToast('Failed to copy link', 'error');
                }
                document.body.removeChild(textArea);
            }
        }

        // Toast notification function
        function showToast(message, type = 'info') {
            const toastContainer = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `w-96 bg-white shadow-xl rounded-xl pointer-events-auto ring-1 ring-black ring-opacity-5 transform transition-all duration-300 translate-x-0`;
            
            const bgColor = type === 'error' ? 'bg-red-50 border-l-4 border-red-400' : 
                           type === 'success' ? 'bg-green-50 border-l-4 border-green-400' : 
                           'bg-blue-50 border-l-4 border-blue-400';
            
            const iconColor = type === 'error' ? 'text-red-500' : 
                             type === 'success' ? 'text-green-500' : 
                             'text-blue-500';
            
            const icon = type === 'error' ? 'fas fa-exclamation-circle' : 
                        type === 'success' ? 'fas fa-check-circle' : 
                        'fas fa-info-circle';
            
            toast.innerHTML = `
                <div class="p-5 ${bgColor} rounded-xl">
                    <div class="flex items-start space-x-4">
                        <div class="flex-shrink-0 pt-1">
                            <i class="${icon} ${iconColor} text-xl"></i>
                        </div>
                        <div class="flex-1 min-w-0">
                            <p class="text-sm font-medium text-gray-900 break-words whitespace-pre-wrap leading-relaxed">${message}</p>
                        </div>
                        <div class="flex-shrink-0">
                            <button class="bg-white rounded-full inline-flex text-gray-400 hover:text-gray-600 p-2 hover:bg-gray-100 transition-colors" onclick="this.parentElement.parentElement.parentElement.parentElement.remove()">
                                <i class="fas fa-times text-xs"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
            
            toastContainer.appendChild(toast);
            
            // Auto remove after 8 seconds
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.remove();
                }
            }, 8000);
        }

        // Download form handler
        document.getElementById('downloadForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const url = formData.get('url');
            const format = formData.get('format');
            
            if (!url) {
                showToast('Please enter a YouTube URL', 'error');
                return;
            }
            
            try {
                const response = await fetch('/download', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        url: url,
                        format: format
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showToast('Download started successfully!', 'success');
                    addDownloadTask(result.task_id, url, format);
                    document.getElementById('downloadStatus').classList.remove('hidden');
                } else {
                    showToast(result.error || 'Download failed', 'error');
                }
            } catch (error) {
                showToast('Network error: ' + error.message, 'error');
            }
        });

        // Add download task to UI
        function addDownloadTask(taskId, url, format) {
            const downloadList = document.getElementById('downloadList');
            const taskElement = document.createElement('div');
            taskElement.id = `task-${taskId}`;
            taskElement.className = 'bg-gray-50 p-3 rounded-lg';
            taskElement.innerHTML = `
                <div class="flex items-center justify-between">
                    <div class="flex-1">
                        <div class="text-sm font-medium text-gray-900 truncate">${url}</div>
                        <div class="text-xs text-gray-500">Format: ${format}</div>
                    </div>
                    <div class="ml-4">
                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                            <i class="fas fa-spinner fa-spin mr-1"></i>Pending
                        </span>
                    </div>
                </div>
                <div class="mt-2">
                    <div class="bg-gray-200 rounded-full h-2">
                        <div class="bg-blue-500 h-2 rounded-full transition-all duration-300" style="width: 0%"></div>
                    </div>
                </div>
            `;
            downloadList.appendChild(taskElement);
            downloadTasks[taskId] = taskElement;
            
            // Start polling for status
            pollDownloadStatus(taskId);
        }

        // Poll download status
        async function pollDownloadStatus(taskId) {
            try {
                const response = await fetch(`/status/${taskId}`);
                const status = await response.json();
                
                updateDownloadTask(taskId, status);
                
                if (status.status === 'downloading' || status.status === 'pending') {
                    setTimeout(() => pollDownloadStatus(taskId), 2000);
                } else if (status.status === 'completed') {
                    if (status.filename) {
                        showToast(`Download completed: ${status.title || 'Video'}`, 'success');
                    } else {
                        showToast(`Download completed: ${status.title || 'Video'} (file will appear in Recent Downloads)`, 'success');
                    }
                    // Refresh recent downloads after a short delay
                    setTimeout(() => location.reload(), 3000);
                }
            } catch (error) {
                console.error('Error polling status:', error);
            }
        }

        // Update download task UI
        function updateDownloadTask(taskId, status) {
            const taskElement = downloadTasks[taskId];
            if (!taskElement) return;
            
            const statusSpan = taskElement.querySelector('span');
            const progressBar = taskElement.querySelector('.bg-blue-500');
            
            switch (status.status) {
                case 'pending':
                    statusSpan.innerHTML = '<i class="fas fa-clock mr-1"></i>Pending';
                    statusSpan.className = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800';
                    break;
                case 'downloading':
                    statusSpan.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Downloading';
                    statusSpan.className = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800';
                    progressBar.style.width = `${status.progress || 0}%`;
                    break;
                case 'completed':
                    statusSpan.innerHTML = '<i class="fas fa-check mr-1"></i>Completed';
                    statusSpan.className = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800';
                    progressBar.style.width = '100%';
                    break;
                case 'failed':
                    statusSpan.innerHTML = '<i class="fas fa-times mr-1"></i>Failed';
                    statusSpan.className = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800';
                    showToast(status.error || 'Download failed', 'error');
                    break;
            }
        }
    </script>
</body>
</html>
"""

# Helper functions
def sanitize_youtu_be(url: str) -> str:
    """Accept youtu.be and youtube.com links"""
    url = url.strip()
    if url.startswith("youtu.be/") or url.startswith("https://youtu.be/") or url.startswith("http://youtu.be/"):
        if url.startswith("youtu.be/"):
            url = "https://" + url
        return url
    if "youtube.com" in url:
        return url
    raise ValueError("Only youtube short links or youtube links accepted")

def format_file_size(size_bytes):
    """Convert bytes to human readable format"""
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f} {size_names[i]}"

def get_recent_files():
    """Get list of recent download files"""
    files = []
    try:
        for filename in os.listdir(DOWNLOAD_DIR):
            if filename.endswith(('.mp4', '.mp3', '.webm', '.m4a')):
                file_path = os.path.join(DOWNLOAD_DIR, filename)
                mtime = os.path.getmtime(file_path)
                file_size = os.path.getsize(file_path)
                
                # Extract display name from filename
                display_name = filename
                if '_' in filename:
                    # Split by underscore and take all parts except the last (which is UUID)
                    parts = filename.split('_')
                    if len(parts) > 1:
                        # Remove the UUID part and file extension
                        name_part = '_'.join(parts[:-1])
                        extension = filename.split('.')[-1]
                        display_name = f"{name_part}.{extension}"
                
                files.append({
                    'name': filename,  # Keep original filename for download link
                    'display_name': display_name,  # Human-readable name
                    'date': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M'),
                    'size': file_size,
                    'size_formatted': format_file_size(file_size),
                    'download_url': f"/file/{filename}"
                })
        files.sort(key=lambda x: x['date'], reverse=True)
        return files[:10]  # Return last 10 files
    except:
        return []

def cleanup_old_files():
    """Remove files older than 7 days"""
    try:
        cutoff_time = time.time() - (7 * 24 * 60 * 60)  # 7 days ago
        for filename in os.listdir(DOWNLOAD_DIR):
            file_path = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.getmtime(file_path) < cutoff_time:
                os.remove(file_path)
                print(f"Cleaned up old file: {filename}")
    except Exception as e:
        print(f"Error during cleanup: {e}")

# Download worker function
def download_worker():
    """Background worker to process download queue"""
    while True:
        try:
            task = download_queue.get(timeout=1)
            if task is None:
                break
            
            task_id = task['task_id']
            url = task['url']
            format_key = task['format']
            
            # Update status
            download_status[task_id] = {
                "status": "downloading",
                "progress": 0,
                "filename": "",
                "error": ""
            }
            
            try:
                format_info = FORMATS[format_key]
                uid = uuid.uuid4().hex
                
                # First, get video info to extract title
                info_cmd = [
                    "python3", "-m", "yt_dlp",
                    "--no-playlist",
                    "--print", "title",
                    url
                ]
                
                title_proc = subprocess.run(info_cmd, capture_output=True, text=True, check=False)
                video_title = "Unknown"
                if title_proc.returncode == 0 and title_proc.stdout.strip():
                    video_title = title_proc.stdout.strip()
                    # Clean filename - remove invalid characters
                    clean_title = "".join(c for c in video_title if c.isalnum() or c in (' ', '-', '_')).strip()
                    clean_title = clean_title[:50]  # Limit length
                    if not clean_title:
                        clean_title = "video"
                else:
                    clean_title = "video"
                
                # Update status with title
                download_status[task_id]["title"] = video_title
                
                # Set output template and command based on format
                if format_key == 'audio':
                    # For audio, use specific audio extraction
                    out_template = os.path.join(DOWNLOAD_DIR, f"{clean_title}_{uid}.%(ext)s")
                    cmd = [
                        "python3", "-m", "yt_dlp",
                        "--no-playlist",
                        "--extract-audio",
                        "--audio-format", "mp3",
                        "--audio-quality", "192K",
                        "-o", out_template,
                        url
                    ]
                else:
                    # For video formats
                    out_template = os.path.join(DOWNLOAD_DIR, f"{clean_title}_{uid}.%(ext)s")
                    cmd = [
                        "python3", "-m", "yt_dlp",
                        "--no-playlist",
                        "-f", format_info['format'],
                        "--merge-output-format", format_info['ext'],
                        "-o", out_template,
                        url
                    ]
                
                # Run download
                proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
                
                if proc.returncode == 0:
                    # Find downloaded file with retry mechanism
                    downloaded_file = None
                    max_retries = 10
                    retry_count = 0
                    
                    while retry_count < max_retries and not downloaded_file:
                        try:
                            for f in os.listdir(DOWNLOAD_DIR):
                                # Check if file starts with clean_title or contains uid
                                if (f.startswith(clean_title) and uid in f) or f.startswith(uid):
                                    # Verify it's a valid media file
                                    if f.endswith(('.mp4', '.mp3', '.webm', '.m4a')):
                                        downloaded_file = f
                                        break
                            
                            if not downloaded_file:
                                time.sleep(0.5)  # Wait 500ms before retry
                                retry_count += 1
                        except Exception as e:
                            print(f"Error checking files: {e}")
                            time.sleep(0.5)
                            retry_count += 1
                    
                    if downloaded_file:
                        download_status[task_id] = {
                            "status": "completed",
                            "progress": 100,
                            "filename": downloaded_file,
                            "error": "",
                            "title": video_title
                        }
                    else:
                        # Still not found, but download succeeded - this might be a timing issue
                        download_status[task_id] = {
                            "status": "completed",
                            "progress": 100,
                            "filename": "",
                            "error": "",
                            "title": video_title
                        }
                else:
                    download_status[task_id] = {
                        "status": "failed",
                        "progress": 0,
                        "filename": "",
                        "error": proc.stderr[:500] if proc.stderr else "Unknown error"
                    }
                    
            except Exception as e:
                download_status[task_id] = {
                    "status": "failed",
                    "progress": 0,
                    "filename": "",
                    "error": str(e)
                }
            
            download_queue.task_done()
            
        except queue.Empty:
            continue
        except Exception as e:
            print(f"Worker error: {e}")

# Start background worker
worker_thread = threading.Thread(target=download_worker, daemon=True)
worker_thread.start()

# Routes
@app.route("/")
def index():
    recent_files = get_recent_files()
    return render_template_string(INDEX_HTML, formats=FORMATS, recent_files=recent_files)



@app.route("/download", methods=["POST"])
def download():
    data = request.get_json()
    url = data.get('url', '')
    format_key = data.get('format', 'mp4_best')
    
    try:
        url = sanitize_youtu_be(url)
        task_id = str(uuid.uuid4())
        
        # Add to queue
        download_queue.put({
            'task_id': task_id,
            'url': url,
            'format': format_key
        })
        
        # Initialize status
        download_status[task_id] = {
            "status": "pending",
            "progress": 0,
            "filename": "",
            "error": "",
            "title": ""
        }
        
        return jsonify({"success": True, "task_id": task_id})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/status/<task_id>")
def get_status(task_id):
    status = download_status.get(task_id, {"status": "not_found", "progress": 0, "filename": "", "error": "Task not found"})
    return jsonify(status)

@app.route("/file/<path:filename>")
def serve_file(filename):
    safe_path = safe_join(DOWNLOAD_DIR, filename)
    if not os.path.exists(safe_path):
        return "File not found", 404
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

@app.route("/cleanup")
def cleanup():
    cleanup_old_files()
    return jsonify({"success": True, "message": "Cleanup completed"})

# Periodic cleanup (run every hour)
def periodic_cleanup():
    while True:
        time.sleep(3600)  # 1 hour
        cleanup_old_files()

cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
cleanup_thread.start()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("FLASK_ENV") == "development"
    
    print("Ad-free YT Download starting...")
    print("No authentication required - open to everyone!")
    if debug:
        print(f"Access at: http://127.0.0.1:{port}")
    
    app.run(debug=debug, host="0.0.0.0", port=port)
