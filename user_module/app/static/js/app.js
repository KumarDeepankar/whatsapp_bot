// User Module - File Management Application
const API_BASE = '/api/files';

// State management
const state = {
    files: [],
    loading: false,
    selectedFile: null,
    activeTab: 'upload',
    pendingUploadFile: null,
    uploadedFile: null  // Stores the uploaded file info for step 2
};

// DOM Elements
const elements = {
    uploadInput: null,
    fileList: null,
    modalOverlay: null,
    toastContainer: null,
    sidebar: null,
    fileCount: null,
    browseBtn: null,
    uploadBtn: null,
    selectedFileName: null,
    fileSelectDisplay: null,
    uploadProgress: null,
    // Step 2 elements
    step1Card: null,
    step2Card: null,
    extractPrompt: null,
    extractBtn: null,
    extractionResult: null,
    resultContent: null,
    uploadedFileInfo: null,
    uploadedFileName: null,
    copyResultBtn: null
};

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
    initializeElements();
    setupEventListeners();
    setupTabNavigation();
    setupThemeToggle();
    setupMobileMenu();
    loadFiles();
});

function initializeElements() {
    elements.uploadInput = document.getElementById('uploadInput');
    elements.fileList = document.getElementById('fileList');
    elements.modalOverlay = document.getElementById('modalOverlay');
    elements.toastContainer = document.getElementById('toastContainer');
    elements.sidebar = document.getElementById('sidebar');
    elements.fileCount = document.getElementById('fileCount');
    elements.browseBtn = document.getElementById('browseBtn');
    elements.uploadBtn = document.getElementById('uploadBtn');
    elements.selectedFileName = document.getElementById('selectedFileName');
    elements.fileSelectDisplay = document.getElementById('fileSelectDisplay');
    elements.uploadProgress = document.getElementById('uploadProgress');
    // Step 2 elements
    elements.step1Card = document.getElementById('step1Card');
    elements.step2Card = document.getElementById('step2Card');
    elements.extractPrompt = document.getElementById('extractPrompt');
    elements.extractBtn = document.getElementById('extractBtn');
    elements.extractionResult = document.getElementById('extractionResult');
    elements.resultContent = document.getElementById('resultContent');
    elements.uploadedFileInfo = document.getElementById('uploadedFileInfo');
    elements.uploadedFileName = document.getElementById('uploadedFileName');
    elements.copyResultBtn = document.getElementById('copyResultBtn');
    elements.startNewContainer = document.getElementById('startNewContainer');
    elements.startNewBtn = document.getElementById('startNewBtn');
}

function setupEventListeners() {
    // Browse button click - opens file dialog
    if (elements.browseBtn) {
        elements.browseBtn.addEventListener('click', () => elements.uploadInput.click());
    }

    // File input change - user selected a file
    if (elements.uploadInput) {
        elements.uploadInput.addEventListener('change', handleFileSelect);
    }

    // Upload button click - actually upload the file
    if (elements.uploadBtn) {
        elements.uploadBtn.addEventListener('click', handleUploadClick);
    }

    // Extract button click - run LLM extraction
    if (elements.extractBtn) {
        elements.extractBtn.addEventListener('click', handleExtractClick);
    }

    // Copy result button
    if (elements.copyResultBtn) {
        elements.copyResultBtn.addEventListener('click', copyExtractionResult);
    }

    // Start new button - refresh the page
    if (elements.startNewBtn) {
        elements.startNewBtn.addEventListener('click', () => {
            window.location.reload();
        });
    }

    // Modal close events
    if (elements.modalOverlay) {
        elements.modalOverlay.addEventListener('click', (e) => {
            if (e.target === elements.modalOverlay) {
                closeModal();
            }
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
            closeMobileMenu();
        }
    });

    // Refresh button
    document.getElementById('refreshBtn')?.addEventListener('click', loadFiles);

    // Sync from S3 button
    document.getElementById('syncBtn')?.addEventListener('click', syncFromS3);
}

function setupTabNavigation() {
    // Desktop sidebar tabs
    const navTabs = document.querySelectorAll('.nav-tab[data-tab]');
    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.dataset.tab;
            switchTab(tabId);
        });
    });

    // Mobile bottom nav tabs
    const mobileNavItems = document.querySelectorAll('.mobile-nav-item[data-tab]');
    mobileNavItems.forEach(item => {
        item.addEventListener('click', () => {
            const tabId = item.dataset.tab;
            switchTab(tabId);
        });
    });
}

function switchTab(tabId) {
    state.activeTab = tabId;

    // Update sidebar nav tabs
    document.querySelectorAll('.nav-tab[data-tab]').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabId);
        tab.setAttribute('aria-selected', tab.dataset.tab === tabId);
    });

    // Update mobile nav items
    document.querySelectorAll('.mobile-nav-item[data-tab]').forEach(item => {
        item.classList.toggle('active', item.dataset.tab === tabId);
    });

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tabId}`);
    });

    // Close mobile menu when switching tabs
    closeMobileMenu();
}

function setupThemeToggle() {
    const toggleTheme = document.getElementById('toggleTheme');
    if (toggleTheme) {
        // Check for saved theme preference
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            document.documentElement.setAttribute('data-theme', savedTheme);
        }

        toggleTheme.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        });
    }
}

function setupMobileMenu() {
    const menuToggle = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');

    if (menuToggle && sidebar) {
        menuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            // Create or toggle overlay
            let overlay = document.querySelector('.sidebar-overlay');
            if (!overlay) {
                overlay = document.createElement('div');
                overlay.className = 'sidebar-overlay';
                overlay.addEventListener('click', closeMobileMenu);
                document.body.appendChild(overlay);
            }
            overlay.classList.toggle('active', sidebar.classList.contains('open'));
        });
    }
}

function closeMobileMenu() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('active');
}

// File selection handler - just selects the file, doesn't upload
function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        const file = files[0];
        const allowedTypes = ['jpg', 'jpeg', 'pdf', 'txt', 'json'];
        const extension = file.name.split('.').pop().toLowerCase();

        if (!allowedTypes.includes(extension)) {
            showToast(`File type .${extension} not allowed. Allowed types: ${allowedTypes.join(', ')}`, 'error');
            resetFileSelection();
            return;
        }

        const maxSize = 50 * 1024 * 1024; // 50MB
        if (file.size > maxSize) {
            showToast('File size exceeds 50MB limit', 'error');
            resetFileSelection();
            return;
        }

        // Store the file for upload
        state.pendingUploadFile = file;

        // Update UI to show selected file
        if (elements.selectedFileName) {
            elements.selectedFileName.textContent = file.name;
        }
        if (elements.fileSelectDisplay) {
            elements.fileSelectDisplay.classList.add('has-file');
        }
        if (elements.uploadBtn) {
            elements.uploadBtn.disabled = false;
        }
    }
}

// Reset file selection UI
function resetFileSelection() {
    state.pendingUploadFile = null;
    if (elements.uploadInput) {
        elements.uploadInput.value = '';
    }
    if (elements.selectedFileName) {
        elements.selectedFileName.textContent = 'No file selected';
    }
    if (elements.fileSelectDisplay) {
        elements.fileSelectDisplay.classList.remove('has-file');
    }
    if (elements.uploadBtn) {
        elements.uploadBtn.disabled = true;
    }
    if (elements.uploadProgress) {
        elements.uploadProgress.style.display = 'none';
    }
}

// Upload button click handler
function handleUploadClick() {
    if (state.pendingUploadFile) {
        uploadFile(state.pendingUploadFile);
    }
}

// API Functions
async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        // Show progress
        if (elements.uploadBtn) {
            elements.uploadBtn.disabled = true;
            elements.uploadBtn.innerHTML = '<span class="spinner"></span> Uploading...';
        }
        if (elements.uploadProgress) {
            elements.uploadProgress.style.display = 'block';
            const progressFill = document.getElementById('progressFill');
            const uploadStatus = document.getElementById('uploadStatus');
            if (progressFill) progressFill.style.width = '50%';
            if (uploadStatus) uploadStatus.textContent = `Uploading ${file.name}...`;
        }

        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            // Show 100% progress briefly
            const progressFill = document.getElementById('progressFill');
            if (progressFill) progressFill.style.width = '100%';

            showToast(`File "${file.name}" uploaded successfully`, 'success');

            // Store uploaded file info for step 2
            state.uploadedFile = {
                s3_key: data.s3_key,
                filename: data.filename,
                file_type: data.file_type
            };

            // Update UI - show uploaded file info
            if (elements.uploadedFileInfo) {
                elements.uploadedFileInfo.style.display = 'block';
            }
            if (elements.uploadedFileName) {
                elements.uploadedFileName.textContent = `${data.filename} uploaded successfully`;
            }

            // Mark step 1 as completed
            if (elements.step1Card) {
                elements.step1Card.classList.add('completed');
            }

            // Enable step 2
            enableStep2();

            // Hide file selection UI
            if (elements.fileSelectDisplay) {
                elements.fileSelectDisplay.style.display = 'none';
            }
            if (elements.browseBtn) {
                elements.browseBtn.style.display = 'none';
            }
            if (elements.uploadBtn) {
                elements.uploadBtn.style.display = 'none';
            }
            if (elements.uploadProgress) {
                elements.uploadProgress.style.display = 'none';
            }

            loadFiles();
        } else {
            throw new Error(data.detail || 'Upload failed');
        }
    } catch (error) {
        showToast(`Upload failed: ${error.message}`, 'error');
        // Reset upload button on error
        if (elements.uploadBtn) {
            elements.uploadBtn.disabled = state.pendingUploadFile ? false : true;
            elements.uploadBtn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                Upload File
            `;
        }
    }
}

// Enable Step 2 after upload
function enableStep2() {
    if (elements.step2Card) {
        elements.step2Card.classList.remove('disabled');
        elements.step2Card.classList.add('active');
    }
    if (elements.extractPrompt) {
        elements.extractPrompt.disabled = false;
    }
    if (elements.extractBtn) {
        elements.extractBtn.disabled = false;
    }
    // Enable format radio buttons
    document.querySelectorAll('input[name="extractFormat"]').forEach(radio => {
        radio.disabled = false;
    });
}

// Handle extract button click
async function handleExtractClick() {
    if (!state.uploadedFile || !state.uploadedFile.s3_key) {
        showToast('Please upload a file first', 'error');
        // Reset to step 1
        resetProcessFlow();
        return;
    }

    const prompt = elements.extractPrompt?.value?.trim();
    if (!prompt) {
        showToast('Please enter a prompt', 'warning');
        elements.extractPrompt?.focus();
        return;
    }

    const selectedFormat = document.querySelector('input[name="extractFormat"]:checked');
    const format = selectedFormat?.value || 'text';

    try {
        // Show loading state
        if (elements.extractBtn) {
            elements.extractBtn.disabled = true;
            elements.extractBtn.innerHTML = '<span class="spinner"></span> Extracting...';
        }

        const response = await fetch(`${API_BASE}/llm-extract`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                s3_key: state.uploadedFile.s3_key,
                prompt: prompt,
                output_format: format
            })
        });

        const data = await response.json();

        if (data.status === 'completed' && data.result) {
            // Show result
            displayExtractionResult(data.result, format);
            showToast('Extraction completed successfully', 'success');
        } else {
            throw new Error(data.message || 'Extraction failed');
        }
    } catch (error) {
        showToast(`Extraction failed: ${error.message}`, 'error');
    } finally {
        // Reset button
        if (elements.extractBtn) {
            elements.extractBtn.disabled = false;
            elements.extractBtn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Extract with LLM
            `;
        }
    }
}

// Display extraction result
function displayExtractionResult(result, format) {
    if (elements.extractionResult) {
        elements.extractionResult.style.display = 'block';
    }
    if (elements.resultContent) {
        if (format === 'json') {
            try {
                const parsed = JSON.parse(result);
                elements.resultContent.textContent = JSON.stringify(parsed, null, 2);
            } catch {
                elements.resultContent.textContent = result;
            }
        } else {
            elements.resultContent.textContent = result;
        }
    }
    // Store result for copying
    state.extractionResult = result;

    // Show "Process Another File" button
    if (elements.startNewContainer) {
        elements.startNewContainer.style.display = 'block';
    }

    // Mark step 2 as completed
    if (elements.step2Card) {
        elements.step2Card.classList.remove('active');
        elements.step2Card.classList.add('completed');
    }
}

// Reset the process flow to start fresh
function resetProcessFlow() {
    // Reset state
    state.uploadedFile = null;
    state.pendingUploadFile = null;
    state.extractionResult = null;

    // Reset Step 1 UI
    if (elements.step1Card) {
        elements.step1Card.classList.remove('completed');
    }
    if (elements.uploadedFileInfo) {
        elements.uploadedFileInfo.style.display = 'none';
    }
    if (elements.fileSelectDisplay) {
        elements.fileSelectDisplay.style.display = 'flex';
        elements.fileSelectDisplay.classList.remove('has-file');
    }
    if (elements.selectedFileName) {
        elements.selectedFileName.textContent = 'No file selected';
    }
    if (elements.browseBtn) {
        elements.browseBtn.style.display = 'inline-flex';
    }
    if (elements.uploadBtn) {
        elements.uploadBtn.style.display = 'inline-flex';
        elements.uploadBtn.disabled = true;
    }
    if (elements.uploadInput) {
        elements.uploadInput.value = '';
    }

    // Reset Step 2 UI
    if (elements.step2Card) {
        elements.step2Card.classList.add('disabled');
        elements.step2Card.classList.remove('active', 'completed');
    }
    if (elements.extractPrompt) {
        elements.extractPrompt.value = '';
        elements.extractPrompt.disabled = true;
    }
    if (elements.extractBtn) {
        elements.extractBtn.disabled = true;
    }
    if (elements.extractionResult) {
        elements.extractionResult.style.display = 'none';
    }
    if (elements.resultContent) {
        elements.resultContent.textContent = '';
    }

    // Disable format radio buttons
    document.querySelectorAll('input[name="extractFormat"]').forEach(radio => {
        radio.disabled = true;
    });
    // Reset to text format
    const textRadio = document.querySelector('input[name="extractFormat"][value="text"]');
    if (textRadio) textRadio.checked = true;

    // Hide start new button
    if (elements.startNewContainer) {
        elements.startNewContainer.style.display = 'none';
    }
}

// Copy extraction result
function copyExtractionResult() {
    if (state.extractionResult) {
        navigator.clipboard.writeText(state.extractionResult).then(() => {
            showToast('Copied to clipboard', 'success');
        }).catch(() => {
            showToast('Failed to copy', 'error');
        });
    }
}

async function loadFiles() {
    try {
        state.loading = true;
        renderFileList();

        const response = await fetch(`${API_BASE}/list`);
        const data = await response.json();

        if (response.ok) {
            state.files = data.files;
            // Update file count badge
            if (elements.fileCount) {
                elements.fileCount.textContent = data.total_count;
            }
        } else {
            throw new Error(data.detail || 'Failed to load files');
        }
    } catch (error) {
        showToast(`Failed to load files: ${error.message}`, 'error');
        state.files = [];
    } finally {
        state.loading = false;
        renderFileList();
    }
}

async function syncFromS3() {
    const syncBtn = document.getElementById('syncBtn');

    try {
        // Show loading state
        if (syncBtn) {
            syncBtn.disabled = true;
            syncBtn.innerHTML = '<span class="spinner"></span> Syncing...';
        }

        const response = await fetch(`${API_BASE}/sync`, {
            method: 'POST'
        });
        const data = await response.json();

        if (response.ok) {
            if (data.synced > 0) {
                showToast(`Synced ${data.synced} files from S3`, 'success');
            } else if (data.skipped > 0) {
                showToast(`All ${data.skipped} files already in database`, 'info');
            } else {
                showToast('No files found in S3 to sync', 'info');
            }

            // Reload files list
            await loadFiles();
        } else {
            throw new Error(data.detail || 'Sync failed');
        }
    } catch (error) {
        showToast(`Sync failed: ${error.message}`, 'error');
    } finally {
        // Reset button state
        if (syncBtn) {
            syncBtn.disabled = false;
            syncBtn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                </svg>
                Sync S3
            `;
        }
    }
}

async function processFile(s3Key, processingType) {
    try {
        const btn = document.querySelector(`[data-s3-key="${CSS.escape(s3Key)}"][data-action="${processingType}"]`);
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span>';
        }

        const response = await fetch(`${API_BASE}/process`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                s3_key: s3Key,
                processing_type: processingType
            })
        });

        const data = await response.json();

        if (data.status === 'completed') {
            showToast(`File processed successfully`, 'success');

            if (processingType === 'text_extract' && data.result) {
                showExtractedTextModal(data.result);
            }

            loadFiles();
        } else {
            throw new Error(data.message || 'Processing failed');
        }
    } catch (error) {
        showToast(`Processing failed: ${error.message}`, 'error');
        loadFiles();
    }
}

async function deleteFile(s3Key, filename) {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/${encodeURIComponent(s3Key)}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (response.ok) {
            showToast(`File "${filename}" deleted`, 'success');
            loadFiles();
        } else {
            throw new Error(data.detail || 'Delete failed');
        }
    } catch (error) {
        showToast(`Delete failed: ${error.message}`, 'error');
    }
}

async function viewExtractedText(s3Key) {
    try {
        const response = await fetch(`${API_BASE}/info/${encodeURIComponent(s3Key)}`);
        const data = await response.json();

        if (response.ok && data.extracted_text) {
            showExtractedTextModal(data.extracted_text);
        } else {
            showToast('No extracted text available', 'warning');
        }
    } catch (error) {
        showToast(`Failed to load extracted text: ${error.message}`, 'error');
    }
}

// Re-index file to WhatsApp Knowledge Base
async function reindexFile(s3Key, filename) {
    const btn = event.target.closest('button');

    try {
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Indexing...';
        }

        const response = await fetch(`${KB_API_BASE}/reindex/${encodeURIComponent(s3Key)}`, {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast(`Successfully indexed "${filename}" to knowledge base (${data.indexed_chunks} chunks)`, 'success');
            // Refresh file list to update indexed status
            loadFiles();
        } else {
            throw new Error(data.detail || data.message || 'Re-indexing failed');
        }
    } catch (error) {
        showToast(`Re-index failed: ${error.message}`, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Re-Index
            `;
        }
    }
}

// Render Functions
function renderFileList() {
    if (state.loading) {
        elements.fileList.innerHTML = `
            <div class="empty-state">
                <div class="spinner"></div>
                <p style="margin-top: 1rem;">Loading files...</p>
            </div>
        `;
        return;
    }

    if (state.files.length === 0) {
        elements.fileList.innerHTML = `
            <div class="empty-state">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
                <p>No files uploaded yet</p>
                <p class="file-types">Upload JPG, PDF, TXT, or JSON files to get started</p>
            </div>
        `;
        return;
    }

    elements.fileList.innerHTML = state.files.map(file => renderFileItem(file)).join('');
}

function renderFileItem(file) {
    const sizeStr = formatFileSize(file.size);
    const dateStr = formatDate(file.upload_time);
    const statusBadge = getStatusBadge(file);
    const isProcessed = file.processing_status === 'completed';
    const hasExtractedText = file.extracted_text && file.extracted_text.length > 0;
    const isIndexed = file.indexed === true;

    return `
        <div class="file-item" data-s3-key="${escapeHtml(file.s3_key)}">
            <div class="file-icon ${file.file_type.toLowerCase()}">${file.file_type.toUpperCase()}</div>
            <div class="file-info">
                <div class="file-name" title="${escapeHtml(file.filename)}">${escapeHtml(file.filename)}</div>
                <div class="file-meta">
                    <span>${sizeStr}</span>
                    <span>${dateStr}</span>
                    ${statusBadge}
                    ${isIndexed ? '<span class="badge badge-indexed">KB Indexed</span>' : ''}
                </div>
            </div>
            <div class="file-actions">
                ${!isProcessed ? `
                    <button class="btn btn-sm btn-primary"
                            onclick="openLLMExtractModal('${escapeHtml(file.s3_key)}', '${escapeHtml(file.filename)}')"
                            title="Extract with custom prompt using LLM">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        LLM Extract
                    </button>
                ` : ''}
                ${hasExtractedText ? `
                    <button class="btn btn-sm btn-secondary"
                            onclick="viewExtractedText('${escapeHtml(file.s3_key)}')"
                            title="View extracted text">
                        View Text
                    </button>
                    <button class="btn btn-sm btn-warning"
                            onclick="reindexFile('${escapeHtml(file.s3_key)}', '${escapeHtml(file.filename)}')"
                            title="Re-index to WhatsApp Knowledge Base">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        ${isIndexed ? 'Re-Index' : 'Index to KB'}
                    </button>
                ` : ''}
                <button class="btn btn-sm btn-danger btn-icon"
                        onclick="deleteFile('${escapeHtml(file.s3_key)}', '${escapeHtml(file.filename)}')"
                        title="Delete file"
                        aria-label="Delete ${escapeHtml(file.filename)}">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                </button>
            </div>
        </div>
    `;
}

function getStatusBadge(file) {
    const status = file.processing_status;
    const type = file.processing_type;

    if (status === 'pending') {
        return '<span class="badge badge-pending">Pending</span>';
    } else if (status === 'processing') {
        return '<span class="badge badge-processing">Processing...</span>';
    } else if (status === 'completed') {
        let typeLabel = 'Processed';
        if (type === 'text_extract') {
            typeLabel = 'Text Extracted';
        } else if (type === 'llm_extract') {
            typeLabel = 'Processed';
        } else if (type === 'indexing') {
            typeLabel = 'Processed';
        }
        return `<span class="badge badge-completed">${typeLabel}</span>`;
    } else if (status === 'failed') {
        return '<span class="badge badge-failed">Failed</span>';
    }
    return '';
}

// Modal Functions
function showExtractedTextModal(text) {
    const modalBody = elements.modalOverlay.querySelector('.modal-body');
    modalBody.innerHTML = `
        <div class="extracted-text">${escapeHtml(text)}</div>
    `;

    const modalTitle = elements.modalOverlay.querySelector('.modal-title');
    modalTitle.textContent = 'Extracted Text';

    elements.modalOverlay.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    elements.modalOverlay.classList.remove('active');
    document.body.style.overflow = '';
}

// Toast Notifications
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            ${type === 'success' ?
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />' :
                type === 'error' ?
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />' :
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />'
            }
        </svg>
        <span>${escapeHtml(message)}</span>
    `;

    elements.toastContainer.appendChild(toast);

    // Auto remove after 5 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// Utility Functions
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;

    // Within last 24 hours
    if (diff < 24 * 60 * 60 * 1000) {
        const hours = Math.floor(diff / (60 * 60 * 1000));
        if (hours < 1) {
            const minutes = Math.floor(diff / (60 * 1000));
            return minutes < 1 ? 'Just now' : `${minutes}m ago`;
        }
        return `${hours}h ago`;
    }

    // Within last week
    if (diff < 7 * 24 * 60 * 60 * 1000) {
        const days = Math.floor(diff / (24 * 60 * 60 * 1000));
        return `${days}d ago`;
    }

    // Otherwise show date
    return date.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// LLM Extract Modal Functions
let currentLLMExtractFile = null;

function openLLMExtractModal(s3Key, filename) {
    console.log('openLLMExtractModal called with:', s3Key, filename);
    currentLLMExtractFile = { s3Key, filename };

    const modal = document.getElementById('llmExtractModal');
    console.log('Modal element:', modal);
    const filenameDisplay = document.getElementById('llmFileName');
    const promptInput = document.getElementById('llmPrompt');

    if (filenameDisplay) {
        filenameDisplay.textContent = filename;
    }

    // Reset form
    if (promptInput) {
        promptInput.value = '';
    }

    // Reset radio buttons to 'text'
    const textRadio = document.querySelector('input[name="outputFormat"][value="text"]');
    if (textRadio) {
        textRadio.checked = true;
    }

    // Show modal
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
        // Focus on prompt input
        setTimeout(() => promptInput?.focus(), 100);
    }
}

function closeLLMModal() {
    const modal = document.getElementById('llmExtractModal');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
    currentLLMExtractFile = null;
}

async function executeLLMExtract() {
    if (!currentLLMExtractFile || !currentLLMExtractFile.s3Key) {
        showToast('No file selected', 'error');
        return;
    }

    const promptInput = document.getElementById('llmPrompt');
    const selectedFormat = document.querySelector('input[name="outputFormat"]:checked');
    const executeBtn = document.getElementById('llmExtractBtn');

    const prompt = promptInput?.value?.trim();

    if (!prompt) {
        showToast('Please enter a prompt', 'warning');
        promptInput?.focus();
        return;
    }

    const format = selectedFormat?.value || 'text';

    // Save file info before any async operations
    const fileInfo = { ...currentLLMExtractFile };

    try {
        // Show loading state
        if (executeBtn) {
            executeBtn.disabled = true;
            executeBtn.innerHTML = '<span class="spinner"></span> Processing...';
        }

        const response = await fetch(`${API_BASE}/llm-extract`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                s3_key: fileInfo.s3Key,
                prompt: prompt,
                output_format: format
            })
        });

        const data = await response.json();

        if (data.status === 'completed' && data.result) {
            // Close the LLM modal
            closeLLMModal();

            // Show result in the main modal (use saved fileInfo)
            showLLMResultModal(data.result, format, fileInfo.filename);

            showToast('LLM extraction completed successfully', 'success');

            // Reload files to update status
            loadFiles();
        } else {
            throw new Error(data.message || 'LLM extraction failed');
        }
    } catch (error) {
        showToast(`LLM extraction failed: ${error.message}`, 'error');
    } finally {
        // Reset button state
        if (executeBtn) {
            executeBtn.disabled = false;
            executeBtn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Extract
            `;
        }
    }
}

function showLLMResultModal(result, format, filename) {
    const modalBody = elements.modalOverlay.querySelector('.modal-body');
    const modalTitle = elements.modalOverlay.querySelector('.modal-title');

    modalTitle.textContent = `LLM Extract Result - ${filename}`;

    let formattedResult = escapeHtml(result);

    // Format based on output type
    if (format === 'json') {
        try {
            const parsed = JSON.parse(result);
            formattedResult = `<pre class="json-result">${escapeHtml(JSON.stringify(parsed, null, 2))}</pre>`;
        } catch {
            formattedResult = `<pre class="json-result">${escapeHtml(result)}</pre>`;
        }
    } else if (format === 'markdown') {
        // Basic markdown rendering - just preserve formatting
        formattedResult = `<div class="markdown-result">${escapeHtml(result).replace(/\n/g, '<br>')}</div>`;
    } else {
        formattedResult = `<div class="extracted-text">${escapeHtml(result)}</div>`;
    }

    modalBody.innerHTML = `
        <div class="llm-result-container">
            <div class="result-actions">
                <button class="btn btn-sm btn-secondary" onclick="copyToClipboard(\`${escapeHtml(result).replace(/`/g, '\\`')}\`)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    Copy
                </button>
            </div>
            ${formattedResult}
        </div>
    `;

    elements.modalOverlay.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard', 'success');
    }).catch(() => {
        showToast('Failed to copy to clipboard', 'error');
    });
}

// Handle LLM modal close on overlay click
document.addEventListener('click', (e) => {
    const llmModal = document.getElementById('llmExtractModal');
    if (e.target === llmModal) {
        closeLLMModal();
    }
});

// Handle Enter key in prompt input
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.ctrlKey) {
        const llmModal = document.getElementById('llmExtractModal');
        if (llmModal && llmModal.classList.contains('active')) {
            executeLLMExtract();
        }
    }
});

// ========================
// Knowledge Base Functions
// ========================

const KB_API_BASE = '/api/knowledge-base';

// Onboarding state
let onboardingState = {
    currentStep: 1,
    filename: '',
    fileType: '',
    fileSize: 0,
    s3Key: '',
    contentB64: '',
    extractedText: '',
    chunks: [],
    embeddedChunks: []
};

// Initialize onboarding UI
function initOnboardingUI() {
    const uploadZone = document.getElementById('kbUploadZone');
    const fileInput = document.getElementById('kbFileInput');

    if (uploadZone && fileInput) {
        // Click to upload
        uploadZone.addEventListener('click', () => fileInput.click());

        // Drag and drop
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });

        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('dragover');
        });

        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                fileInput.files = e.dataTransfer.files;
                handleFileSelection(e.dataTransfer.files[0]);
            }
        });

        // File input change
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFileSelection(e.target.files[0]);
            }
        });
    }

    // Step buttons
    document.getElementById('step1NextBtn')?.addEventListener('click', executeStep1);
    document.getElementById('step2NextBtn')?.addEventListener('click', executeStep2);
    document.getElementById('step3NextBtn')?.addEventListener('click', executeStep3);
    document.getElementById('step4NextBtn')?.addEventListener('click', executeStep4);
    document.getElementById('step5NextBtn')?.addEventListener('click', executeStep5);
}

function handleFileSelection(file) {
    const fileInfo = document.getElementById('selectedFileInfo');
    const fileName = document.getElementById('selectedFileName');
    const fileSize = document.getElementById('selectedFileSize');
    const nextBtn = document.getElementById('step1NextBtn');

    if (file) {
        fileName.textContent = file.name;
        fileSize.textContent = formatFileSize(file.size);
        fileInfo.style.display = 'block';
        nextBtn.disabled = false;
        onboardingState.selectedFile = file;
    }
}

function clearSelectedFile() {
    const fileInput = document.getElementById('kbFileInput');
    const fileInfo = document.getElementById('selectedFileInfo');
    const nextBtn = document.getElementById('step1NextBtn');

    fileInput.value = '';
    fileInfo.style.display = 'none';
    nextBtn.disabled = true;
    onboardingState.selectedFile = null;
}

function goToStep(step) {
    // Update progress indicators
    document.querySelectorAll('.progress-step').forEach((el, idx) => {
        if (idx + 1 < step) {
            el.classList.add('completed');
            el.classList.remove('active');
        } else if (idx + 1 === step) {
            el.classList.add('active');
            el.classList.remove('completed');
        } else {
            el.classList.remove('active', 'completed');
        }
    });

    // Update step panels
    document.querySelectorAll('.step-panel').forEach((panel, idx) => {
        if (idx + 1 === step) {
            panel.classList.add('active');
        } else {
            panel.classList.remove('active');
        }
    });

    onboardingState.currentStep = step;
}

async function executeStep1() {
    const btn = document.getElementById('step1NextBtn');
    const file = onboardingState.selectedFile;

    if (!file) {
        showToast('Please select a file first', 'warning');
        return;
    }

    try {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Uploading...';

        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${KB_API_BASE}/onboard/step1-upload`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Upload failed');
        }

        // Store state (including S3 key and file size for later steps)
        onboardingState.filename = data.filename;
        onboardingState.fileType = data.file_type;
        onboardingState.fileSize = data.file_size;
        onboardingState.s3Key = data.s3_key;
        onboardingState.contentB64 = data.content_b64;

        showToast(data.message, 'success');

        // Mark step 1 as completed and go to step 2
        goToStep(2);

    } catch (error) {
        showToast(`Upload failed: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Upload & Validate <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>';
    }
}

async function executeStep2() {
    const btn = document.getElementById('step2NextBtn');
    const previewEl = document.getElementById('extractionPreview');
    const statsEl = document.getElementById('extractionStats');

    try {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Extracting...';
        previewEl.innerHTML = '<div class="preview-placeholder"><div class="spinner"></div><p>Extracting text...</p></div>';

        const formData = new FormData();
        formData.append('filename', onboardingState.filename);
        formData.append('content_b64', onboardingState.contentB64);
        formData.append('s3_key', onboardingState.s3Key);

        const response = await fetch(`${KB_API_BASE}/onboard/step2-extract`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Extraction failed');
        }

        // Store extracted text
        onboardingState.extractedText = data.text;

        // Update stats
        document.getElementById('extractPages').textContent = data.pages;
        document.getElementById('extractChars').textContent = data.total_chars.toLocaleString();
        document.getElementById('extractWords').textContent = data.total_words.toLocaleString();
        statsEl.style.display = 'flex';

        // Show preview
        previewEl.innerHTML = `<pre class="text-preview">${escapeHtml(data.preview)}</pre>`;

        showToast(data.message, 'success');

        // Go to step 3
        goToStep(3);

    } catch (error) {
        showToast(`Extraction failed: ${error.message}`, 'error');
        previewEl.innerHTML = `<div class="preview-placeholder error"><p>Extraction failed: ${error.message}</p></div>`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Extract Text <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>';
    }
}

async function executeStep3() {
    const btn = document.getElementById('step3NextBtn');
    const previewEl = document.getElementById('chunksPreview');
    const statsEl = document.getElementById('chunksStats');
    const chunkSize = document.getElementById('chunkSize').value;
    const chunkOverlap = document.getElementById('chunkOverlap').value;

    try {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Chunking...';
        previewEl.innerHTML = '<div class="preview-placeholder"><div class="spinner"></div><p>Creating chunks...</p></div>';

        const formData = new FormData();
        formData.append('filename', onboardingState.filename);
        formData.append('text', onboardingState.extractedText);
        formData.append('chunk_size', chunkSize);
        formData.append('chunk_overlap', chunkOverlap);

        const response = await fetch(`${KB_API_BASE}/onboard/step3-chunk`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Chunking failed');
        }

        // Store chunks
        onboardingState.chunks = data.chunks;

        // Update stats
        document.getElementById('totalChunks').textContent = data.stats.total_chunks;
        document.getElementById('avgChunkSize').textContent = `${data.stats.avg_chunk_size} chars`;
        statsEl.style.display = 'flex';

        // Show preview of first 3 chunks
        previewEl.innerHTML = data.chunks_preview.map((chunk, i) => `
            <div class="chunk-preview-item">
                <div class="chunk-header">Chunk ${chunk.index + 1} <span class="chunk-size">${chunk.chars} chars</span></div>
                <div class="chunk-text">${escapeHtml(chunk.preview)}</div>
            </div>
        `).join('') + (data.chunks.length > 3 ? `<div class="more-chunks">+ ${data.chunks.length - 3} more chunks</div>` : '');

        showToast(data.message, 'success');

        // Go to step 4
        goToStep(4);

    } catch (error) {
        showToast(`Chunking failed: ${error.message}`, 'error');
        previewEl.innerHTML = `<div class="preview-placeholder error"><p>Chunking failed: ${error.message}</p></div>`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Create Chunks <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>';
    }
}

async function executeStep4() {
    const btn = document.getElementById('step4NextBtn');
    const progressText = document.getElementById('embeddingProgressText');
    const progressBar = document.getElementById('embeddingProgressBar');
    const statsEl = document.getElementById('embeddingStats');

    try {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Generating...';
        progressText.textContent = `Generating embeddings for ${onboardingState.chunks.length} chunks...`;
        progressBar.style.width = '10%';

        const formData = new FormData();
        formData.append('filename', onboardingState.filename);
        formData.append('chunks_json', JSON.stringify(onboardingState.chunks));

        const response = await fetch(`${KB_API_BASE}/onboard/step4-embed`, {
            method: 'POST',
            body: formData
        });

        progressBar.style.width = '90%';

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Embedding generation failed');
        }

        // Store embedded chunks
        onboardingState.embeddedChunks = data.chunks;

        progressBar.style.width = '100%';
        progressText.textContent = data.message;

        // Update stats
        document.getElementById('embeddingSuccess').textContent = data.successful;
        document.getElementById('embeddingFailed').textContent = data.failed;
        document.getElementById('embeddingDimensions').textContent = data.embedding_dimension;
        statsEl.style.display = 'flex';

        showToast(data.message, 'success');

        // Go to step 5
        goToStep(5);

    } catch (error) {
        showToast(`Embedding failed: ${error.message}`, 'error');
        progressText.textContent = `Failed: ${error.message}`;
        progressBar.style.width = '0%';
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Generate Embeddings <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>';
    }
}

async function executeStep5() {
    const btn = document.getElementById('step5NextBtn');
    const backBtn = document.getElementById('step5BackBtn');
    const anotherBtn = document.getElementById('onboardAnotherBtn');
    const progressText = document.getElementById('indexingProgressText');
    const progressBar = document.getElementById('indexingProgressBar');
    const resultEl = document.getElementById('indexingResult');
    const progressEl = document.getElementById('indexingProgress');

    try {
        btn.disabled = true;
        backBtn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Indexing...';
        progressText.textContent = `Indexing ${onboardingState.embeddedChunks.length} chunks to OpenSearch...`;
        progressBar.style.width = '30%';

        const formData = new FormData();
        formData.append('filename', onboardingState.filename);
        formData.append('file_type', onboardingState.fileType);
        formData.append('file_size', onboardingState.fileSize);
        formData.append('s3_key', onboardingState.s3Key);
        formData.append('extracted_text', onboardingState.extractedText);
        formData.append('chunks_json', JSON.stringify(onboardingState.embeddedChunks));

        const response = await fetch(`${KB_API_BASE}/onboard/step5-index`, {
            method: 'POST',
            body: formData
        });

        progressBar.style.width = '90%';

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Indexing failed');
        }

        progressBar.style.width = '100%';

        // Show success
        progressEl.style.display = 'none';
        resultEl.style.display = 'block';
        document.getElementById('indexingResultMessage').textContent = data.message;

        // Hide step buttons, show "onboard another"
        btn.style.display = 'none';
        backBtn.style.display = 'none';
        anotherBtn.style.display = 'inline-flex';

        // Mark step 5 as completed
        document.querySelector('.progress-step[data-step="5"]').classList.add('completed');

        showToast(data.message, 'success');

        // Refresh KB status
        await loadKnowledgeBaseStatus();

    } catch (error) {
        showToast(`Indexing failed: ${error.message}`, 'error');
        progressText.textContent = `Failed: ${error.message}`;
        progressBar.style.width = '0%';
        backBtn.disabled = false;
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Index to Knowledge Base <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>';
    }
}

function resetOnboarding() {
    // Reset state
    onboardingState = {
        currentStep: 1,
        filename: '',
        fileType: '',
        fileSize: 0,
        s3Key: '',
        contentB64: '',
        extractedText: '',
        chunks: [],
        embeddedChunks: []
    };

    // Reset UI
    clearSelectedFile();

    // Reset step panels
    document.getElementById('extractionStats').style.display = 'none';
    document.getElementById('extractionPreview').innerHTML = '<div class="preview-placeholder"><p>Text will be extracted from your document</p></div>';
    document.getElementById('chunksStats').style.display = 'none';
    document.getElementById('chunksPreview').innerHTML = '<div class="preview-placeholder"><p>Chunks will appear here after processing</p></div>';
    document.getElementById('embeddingStats').style.display = 'none';
    document.getElementById('embeddingProgressText').textContent = 'Ready to generate embeddings';
    document.getElementById('embeddingProgressBar').style.width = '0%';
    document.getElementById('indexingProgress').style.display = 'block';
    document.getElementById('indexingResult').style.display = 'none';
    document.getElementById('indexingProgressText').textContent = 'Ready to index';
    document.getElementById('indexingProgressBar').style.width = '0%';

    // Reset buttons
    document.getElementById('step5NextBtn').style.display = 'inline-flex';
    document.getElementById('step5BackBtn').style.display = 'inline-flex';
    document.getElementById('onboardAnotherBtn').style.display = 'none';

    // Go to step 1
    goToStep(1);
}

// Initialize when DOM ready
document.addEventListener('DOMContentLoaded', () => {
    initOnboardingUI();
});

// Load knowledge base status and documents
async function loadKnowledgeBaseStatus() {
    try {
        const response = await fetch(`${KB_API_BASE}/status`);
        const data = await response.json();

        const statusIndicator = document.getElementById('kbStatusIndicator');
        const statusDot = statusIndicator?.querySelector('.status-dot');
        const statusText = statusIndicator?.querySelector('.status-text');

        if (data.connected) {
            statusDot?.classList.remove('disconnected');
            statusDot?.classList.add('connected');
            statusText.textContent = `Connected to ${data.cluster_name} (v${data.version})`;

            // Update stats
            document.getElementById('kbTotalDocs').textContent = data.index?.unique_documents || 0;
            document.getElementById('kbTotalChunks').textContent = data.index?.total_chunks || 0;
            document.getElementById('kbIndexSize').textContent = data.index?.size_mb ? `${data.index.size_mb} MB` : '0 MB';
            document.getElementById('kbDocCount').textContent = data.index?.unique_documents || 0;
        } else {
            statusDot?.classList.remove('connected');
            statusDot?.classList.add('disconnected');
            statusText.textContent = `Disconnected: ${data.error || 'Unknown error'}`;

            document.getElementById('kbTotalDocs').textContent = '-';
            document.getElementById('kbTotalChunks').textContent = '-';
            document.getElementById('kbIndexSize').textContent = '-';
            document.getElementById('kbDocCount').textContent = '0';
        }

        // Load indexed documents
        await loadIndexedDocuments();

        // Load available files
        await loadAvailableFiles();

    } catch (error) {
        console.error('Failed to load KB status:', error);
        showToast(`Failed to load knowledge base status: ${error.message}`, 'error');
    }
}

async function loadIndexedDocuments() {
    const listEl = document.getElementById('kbDocumentsList');
    if (!listEl) return;

    try {
        const response = await fetch(`${KB_API_BASE}/documents`);
        const data = await response.json();

        if (data.documents && data.documents.length > 0) {
            listEl.innerHTML = data.documents.map(doc => `
                <div class="kb-doc-item">
                    <div class="kb-doc-info">
                        <div class="kb-doc-name">${escapeHtml(doc.filename)}</div>
                        <div class="kb-doc-meta">
                            <span>${doc.chunk_count} chunks</span>
                            <span>${doc.file_type.toUpperCase()}</span>
                            ${doc.indexed_at ? `<span>${formatDate(doc.indexed_at)}</span>` : ''}
                        </div>
                    </div>
                    <div class="kb-doc-actions">
                        <button class="btn btn-sm btn-danger" onclick="removeFromKB('${escapeHtml(doc.s3_key)}', '${escapeHtml(doc.filename)}')">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                            Remove
                        </button>
                    </div>
                </div>
            `).join('');
        } else {
            listEl.innerHTML = `
                <div class="empty-state">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" width="48" height="48">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <p>No documents indexed yet</p>
                    <p class="file-types">Publish files to add them to the knowledge base</p>
                </div>
            `;
        }
    } catch (error) {
        listEl.innerHTML = `<div class="empty-state"><p>Failed to load indexed documents</p></div>`;
    }
}

async function loadAvailableFiles() {
    const listEl = document.getElementById('kbAvailableList');
    if (!listEl) return;

    try {
        // Get all files
        const filesResponse = await fetch(`${API_BASE}/list`);
        const filesData = await filesResponse.json();

        // Get indexed documents
        const kbResponse = await fetch(`${KB_API_BASE}/documents`);
        const kbData = await kbResponse.json();

        const indexedKeys = new Set((kbData.documents || []).map(d => d.s3_key));

        // Filter files that have extracted text and are not already indexed
        const availableFiles = (filesData.files || []).filter(f =>
            f.extracted_text &&
            f.processing_status === 'completed' &&
            !indexedKeys.has(f.s3_key)
        );

        if (availableFiles.length > 0) {
            listEl.innerHTML = availableFiles.map(file => `
                <div class="kb-available-item">
                    <div class="kb-doc-info">
                        <div class="kb-doc-name">${escapeHtml(file.filename)}</div>
                        <div class="kb-doc-meta">
                            <span>${formatFileSize(file.size)}</span>
                            <span>${file.file_type.toUpperCase()}</span>
                        </div>
                    </div>
                    <div class="kb-doc-actions">
                        <button class="btn btn-sm btn-primary" onclick="publishToKB('${escapeHtml(file.s3_key)}', '${escapeHtml(file.filename)}')">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                            </svg>
                            Publish
                        </button>
                    </div>
                </div>
            `).join('');
        } else {
            listEl.innerHTML = `
                <div class="empty-state">
                    <p>No files available to publish</p>
                    <p class="file-types">Extract text from files first, then publish them here</p>
                </div>
            `;
        }
    } catch (error) {
        listEl.innerHTML = `<div class="empty-state"><p>Failed to load available files</p></div>`;
    }
}

async function publishToKB(s3Key, filename) {
    const btn = event.target.closest('button');

    try {
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Publishing...';
        }

        const response = await fetch(`${KB_API_BASE}/publish`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ s3_key: s3Key, extract_if_needed: true })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast(`Published "${filename}" to knowledge base (${data.indexed_chunks} chunks)`, 'success');
            await loadKnowledgeBaseStatus();
        } else {
            throw new Error(data.detail || data.message || 'Publish failed');
        }
    } catch (error) {
        showToast(`Failed to publish: ${error.message}`, 'error');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                Publish
            `;
        }
    }
}

async function removeFromKB(s3Key, filename) {
    if (!confirm(`Remove "${filename}" from the knowledge base?`)) {
        return;
    }

    try {
        const response = await fetch(`${KB_API_BASE}/documents/${encodeURIComponent(s3Key)}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast(`Removed "${filename}" from knowledge base`, 'success');
            await loadKnowledgeBaseStatus();
        } else {
            throw new Error(data.detail || 'Remove failed');
        }
    } catch (error) {
        showToast(`Failed to remove: ${error.message}`, 'error');
    }
}

async function publishAllToKB() {
    const btn = document.getElementById('publishAllBtn');

    try {
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Publishing all files...';
        }

        const response = await fetch(`${KB_API_BASE}/publish-all`, {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok) {
            if (data.published > 0) {
                showToast(`Published ${data.published} of ${data.total} files to knowledge base`, 'success');
            } else {
                showToast(data.message || 'No files to publish', 'info');
            }
            await loadKnowledgeBaseStatus();
        } else {
            throw new Error(data.detail || 'Publish all failed');
        }
    } catch (error) {
        showToast(`Failed to publish all: ${error.message}`, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                Publish All Extracted Files
            `;
        }
    }
}

async function createKBIndex() {
    const btn = document.getElementById('createIndexBtn');

    try {
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Creating...';
        }

        const response = await fetch(`${KB_API_BASE}/index/create`, {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast(data.message, 'success');
            await loadKnowledgeBaseStatus();
        } else {
            throw new Error(data.detail || data.message || 'Failed to create index');
        }
    } catch (error) {
        showToast(`Failed to create index: ${error.message}`, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
                Create Index
            `;
        }
    }
}

async function deleteKBIndex() {
    if (!confirm('Are you sure you want to delete the entire knowledge base index? This will remove all indexed documents.')) {
        return;
    }

    const btn = document.getElementById('deleteIndexBtn');

    try {
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Deleting...';
        }

        const response = await fetch(`${KB_API_BASE}/index`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast(data.message, 'success');
            await loadKnowledgeBaseStatus();
        } else {
            throw new Error(data.detail || 'Failed to delete index');
        }
    } catch (error) {
        showToast(`Failed to delete index: ${error.message}`, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                Delete Index
            `;
        }
    }
}

async function rebuildAllFromS3() {
    if (!confirm('This will rebuild the entire Knowledge Base from S3.\n\nThis process:\n1. Syncs DB from S3 files\n2. Re-indexes all files with extracted text\n\nThis may take several minutes. Continue?')) {
        return;
    }

    const btn = event.target.closest('button');

    try {
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Rebuilding...';
        }

        showToast('Starting rebuild from S3... This may take a while.', 'info');

        const response = await fetch(`${KB_API_BASE}/rebuild-all?skip_indexed=false`, {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok) {
            const phase1 = data.phase1_sync || {};
            const phase2 = data.phase2_index || {};

            showToast(
                `Rebuild complete!\nDB Sync: ${phase1.synced || 0} files\nIndexed: ${phase2.indexed || 0}, Skipped: ${phase2.skipped || 0}, Failed: ${phase2.failed || 0}`,
                data.success ? 'success' : 'warning'
            );

            // Refresh status
            await loadKnowledgeBaseStatus();
            // Refresh files list
            await loadFiles();
        } else {
            throw new Error(data.detail || 'Rebuild failed');
        }
    } catch (error) {
        showToast(`Rebuild failed: ${error.message}`, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = 'Rebuild All';
        }
    }
}

async function searchKnowledgeBase() {
    const searchInput = document.getElementById('kbSearchInput');
    const resultsEl = document.getElementById('kbSearchResults');
    const query = searchInput?.value?.trim();

    if (!query) {
        showToast('Please enter a search query', 'warning');
        return;
    }

    try {
        resultsEl.innerHTML = `
            <div class="empty-state">
                <div class="spinner"></div>
                <p style="margin-top: 1rem;">Searching...</p>
            </div>
        `;

        const response = await fetch(`${KB_API_BASE}/search?query=${encodeURIComponent(query)}&k=5`);
        const data = await response.json();

        if (response.ok) {
            if (data.results && data.results.length > 0) {
                resultsEl.innerHTML = `
                    <p class="search-results-count">Found ${data.total_results} result(s) for "${escapeHtml(query)}"</p>
                    ${data.results.map((result, i) => `
                        <div class="kb-search-result">
                            <div class="kb-search-result-header">
                                <span class="kb-search-result-filename">${escapeHtml(result.filename)}</span>
                                <span class="kb-search-result-score">Score: ${result.score.toFixed(3)}</span>
                            </div>
                            <div class="kb-search-result-content">${escapeHtml(result.content.substring(0, 300))}${result.content.length > 300 ? '...' : ''}</div>
                        </div>
                    `).join('')}
                `;
            } else {
                resultsEl.innerHTML = `
                    <div class="empty-state">
                        <p>No results found for "${escapeHtml(query)}"</p>
                    </div>
                `;
            }
        } else {
            throw new Error(data.detail || 'Search failed');
        }
    } catch (error) {
        resultsEl.innerHTML = `<div class="empty-state"><p>Search failed: ${error.message}</p></div>`;
        showToast(`Search failed: ${error.message}`, 'error');
    }
}

// Load KB status when switching to the knowledge-base tab
const originalSwitchTab = switchTab;
switchTab = function(tabId) {
    originalSwitchTab(tabId);
    if (tabId === 'knowledge-base') {
        loadKnowledgeBaseStatus();
    }
};

// Make KB functions available globally
window.loadKnowledgeBaseStatus = loadKnowledgeBaseStatus;
window.publishToKB = publishToKB;
window.removeFromKB = removeFromKB;
window.publishAllToKB = publishAllToKB;
window.createKBIndex = createKBIndex;
window.deleteKBIndex = deleteKBIndex;
window.rebuildAllFromS3 = rebuildAllFromS3;
window.searchKnowledgeBase = searchKnowledgeBase;

// Make functions available globally
window.processFile = processFile;
window.deleteFile = deleteFile;
window.viewExtractedText = viewExtractedText;
window.reindexFile = reindexFile;
window.closeModal = closeModal;
window.switchTab = switchTab;
window.openLLMExtractModal = openLLMExtractModal;
window.closeLLMModal = closeLLMModal;
window.executeLLMExtract = executeLLMExtract;
window.copyToClipboard = copyToClipboard;

// Make onboarding functions available globally
window.goToStep = goToStep;
window.clearSelectedFile = clearSelectedFile;
window.resetOnboarding = resetOnboarding;
