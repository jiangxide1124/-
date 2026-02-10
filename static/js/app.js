/**
 * Script Video Generator - Frontend Application
 * Handles script input, scene management, image generation, and UI interactions
 */

// ============================================================
// State Management
// ============================================================

const AppState = {
    scenes: [],
    currentTab: 'script',
    characters: {
        char_1: { name: 'char_1', description: '' },
        char_2: { name: 'char_2', description: '' },
        char_3: { name: 'char_3', description: '' }
    },
    activeCharacter: 'char_1',
    isGenerating: false,
    generationProgress: { completed: 0, total: 0 },
    projectName: '새 프로젝트'
};

// ============================================================
// Toast Notifications
// ============================================================

function showToast(message, type = 'info') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============================================================
// API Calls
// ============================================================

async function apiCall(endpoint, data = null) {
    try {
        const options = {
            method: data ? 'POST' : 'GET',
            headers: { 'Content-Type': 'application/json' }
        };
        if (data) options.body = JSON.stringify(data);

        const response = await fetch(endpoint, options);
        const result = await response.json();

        if (!result.success && result.error) {
            showToast(result.error, 'error');
        }
        return result;
    } catch (error) {
        showToast(`요청 실패: ${error.message}`, 'error');
        return { success: false, error: error.message };
    }
}

// ============================================================
// Tab Navigation
// ============================================================

function initTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    document.querySelector(`.tab[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.add('active');
    AppState.currentTab = tabName;
}

// ============================================================
// Script Editor
// ============================================================

function initScriptEditor() {
    const editor = document.getElementById('scriptEditor');

    editor.addEventListener('input', () => {
        updateScriptStats();
    });

    editor.addEventListener('keydown', (e) => {
        // Update stats on Enter key
        if (e.key === 'Enter') {
            setTimeout(updateScriptStats, 10);
        }
    });

    // Fetch YouTube transcript
    document.getElementById('btnFetchTranscript').addEventListener('click', async () => {
        const url = document.getElementById('youtubeUrl').value.trim();
        if (!url) {
            showToast('YouTube URL을 입력해주세요.', 'error');
            return;
        }

        showToast('자막을 가져오는 중...', 'info');
        const result = await apiCall('/transcript', { url });
        if (result.success) {
            editor.value = result.transcript;
            updateScriptStats();
            showToast(`자막을 가져왔습니다. (${result.language})`, 'success');
        }
    });

    // Analyze script button
    document.getElementById('btnAnalyzeScript').addEventListener('click', () => {
        analyzeScript();
    });
}

function updateScriptStats() {
    const text = document.getElementById('scriptEditor').value;
    const chars = text.length;
    const lines = text ? text.split('\n').length : 0;
    const paragraphs = text ? text.split(/\n\s*\n/).filter(p => p.trim()).length : 0;

    document.getElementById('charCount').textContent = `${chars}자`;
    document.getElementById('lineCount').textContent = `${lines}줄`;
    document.getElementById('sceneEstimate').textContent = `예상 장면: ${paragraphs}개`;
}

// ============================================================
// Script Analysis
// ============================================================

async function analyzeScript() {
    const script = document.getElementById('scriptEditor').value.trim();
    if (!script) {
        showToast('대본을 입력해주세요.', 'error');
        return;
    }

    const splitMode = document.getElementById('splitMode').value;
    const style = document.getElementById('imageStyle')?.value || '';
    const charDesc = AppState.characters[AppState.activeCharacter]?.description || '';

    showToast('대본 분석 중...', 'info');

    const result = await apiCall('/api/analyze-script', {
        script,
        split_mode: splitMode,
        style,
        character_desc: charDesc
    });

    if (result.success) {
        AppState.scenes = result.scenes;
        renderScenes();
        switchTab('scenes');
        showToast(`${result.total}개 장면으로 분석되었습니다.`, 'success');
    }
}

// ============================================================
// Scene Rendering
// ============================================================

function renderScenes() {
    const container = document.getElementById('sceneList');
    const count = document.getElementById('sceneCount');
    count.textContent = `(${AppState.scenes.length}개)`;

    if (AppState.scenes.length === 0) {
        container.innerHTML = `
            <div class="empty-state" id="emptyState">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#555" stroke-width="1.5">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                    <line x1="3" y1="9" x2="21" y2="9"></line>
                    <line x1="9" y1="21" x2="9" y2="9"></line>
                </svg>
                <p>대본을 입력하고 "AI 대본 분석 실행"을 클릭하세요.</p>
                <p class="hint">또는 "1. 대본" 탭에서 대본을 먼저 작성하세요.</p>
            </div>`;
        return;
    }

    container.innerHTML = AppState.scenes.map((scene, idx) => createSceneCard(scene, idx)).join('');

    // Attach event listeners to all scene cards
    attachSceneEventListeners();
}

function createSceneCard(scene, idx) {
    const chars = (scene.characters || ['char_1']).map(c =>
        `<span class="scene-char-tag">${c}</span>`
    ).join(' ');

    const imageContent = scene.image_url
        ? `<img src="${scene.image_url}" alt="장면 ${scene.id}">`
        : `<div class="image-placeholder">
               <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#555" stroke-width="1.5">
                   <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                   <circle cx="8.5" cy="8.5" r="1.5"></circle>
                   <polyline points="21 15 16 10 5 21"></polyline>
               </svg>
               <span>이미지 없음</span>
           </div>`;

    return `
    <div class="scene-card" data-scene-idx="${idx}" data-scene-id="${scene.id}">
        <div class="scene-card-header">
            <div class="scene-card-header-left">
                <span class="scene-number">장면 ${scene.id}</span>
                ${chars}
            </div>
            <div class="scene-card-actions">
                <button class="btn btn-small btn-scene-split" data-idx="${idx}" title="이 장면을 분할">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="12" y1="5" x2="12" y2="19"></line>
                        <line x1="5" y1="12" x2="19" y2="12"></line>
                    </svg>
                </button>
                <button class="btn btn-small btn-scene-delete" data-idx="${idx}" title="장면 삭제">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                </button>
            </div>
        </div>
        <div class="scene-card-body">
            <div class="scene-card-content">
                <div class="scene-field">
                    <div class="scene-field-label">
                        <span>나레이션</span>
                    </div>
                    <textarea class="narration" data-idx="${idx}" data-field="narration" rows="2">${escapeHtml(scene.narration)}</textarea>
                </div>
                <div class="scene-field">
                    <div class="scene-field-label">
                        <span>이미지 프롬프트</span>
                        <div class="field-actions">
                            <button class="btn btn-small btn-regenerate-prompt" data-idx="${idx}" data-type="image" title="이미지 프롬프트 재생성">
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="23 4 23 10 17 10"></polyline>
                                    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                                </svg>
                            </button>
                        </div>
                    </div>
                    <textarea data-idx="${idx}" data-field="image_prompt" rows="3">${escapeHtml(scene.image_prompt)}</textarea>
                </div>
                <div class="scene-field">
                    <div class="scene-field-label">
                        <span>동영상 프롬프트</span>
                        <div class="field-actions">
                            <button class="btn btn-small btn-regenerate-prompt" data-idx="${idx}" data-type="video" title="동영상 프롬프트 재생성">
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="23 4 23 10 17 10"></polyline>
                                    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                                </svg>
                            </button>
                        </div>
                    </div>
                    <textarea data-idx="${idx}" data-field="video_prompt" rows="3">${escapeHtml(scene.video_prompt)}</textarea>
                </div>
            </div>
            <div class="scene-card-image">
                ${imageContent}
                <div class="image-actions">
                    <button class="btn-icon btn-star" data-idx="${idx}" title="즐겨찾기">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2">
                            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                        </svg>
                    </button>
                    <button class="btn-icon btn-regenerate btn-scene-generate" data-idx="${idx}" title="이미지 생성">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="23 4 23 10 17 10"></polyline>
                            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                        </svg>
                    </button>
                    <button class="btn-icon btn-play btn-scene-play" data-idx="${idx}" title="영상 미리보기" style="color: var(--accent-green);">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2">
                            <polygon points="5 3 19 12 5 21 5 3"></polygon>
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    </div>`;
}

function attachSceneEventListeners() {
    // Textarea changes - auto-save to state
    document.querySelectorAll('.scene-card textarea').forEach(textarea => {
        textarea.addEventListener('input', (e) => {
            const idx = parseInt(e.target.dataset.idx);
            const field = e.target.dataset.field;
            if (AppState.scenes[idx]) {
                AppState.scenes[idx][field] = e.target.value;
            }
            autoResizeTextarea(e.target);
        });

        // Auto-resize on load
        autoResizeTextarea(textarea);
    });

    // Split scene buttons
    document.querySelectorAll('.btn-scene-split').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = parseInt(e.currentTarget.dataset.idx);
            splitScene(idx);
        });
    });

    // Delete scene buttons
    document.querySelectorAll('.btn-scene-delete').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = parseInt(e.currentTarget.dataset.idx);
            deleteScene(idx);
        });
    });

    // Generate single image buttons
    document.querySelectorAll('.btn-scene-generate').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = parseInt(e.currentTarget.dataset.idx);
            generateSingleImage(idx);
        });
    });

    // Regenerate prompt buttons
    document.querySelectorAll('.btn-regenerate-prompt').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const idx = parseInt(e.currentTarget.dataset.idx);
            const type = e.currentTarget.dataset.type;
            await regeneratePrompt(idx, type);
        });
    });
}

function autoResizeTextarea(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

// ============================================================
// Scene Operations
// ============================================================

function splitScene(idx) {
    const scene = AppState.scenes[idx];
    if (!scene) return;

    const narration = scene.narration;
    const midPoint = Math.floor(narration.length / 2);

    // Find nearest sentence break
    let splitAt = midPoint;
    const breaks = ['. ', '.\n', '다. ', '다.\n', '요. ', '요.\n'];
    let bestBreak = -1;

    for (const br of breaks) {
        const pos = narration.indexOf(br, Math.floor(midPoint * 0.5));
        if (pos > 0 && pos < midPoint * 1.5) {
            if (bestBreak === -1 || Math.abs(pos - midPoint) < Math.abs(bestBreak - midPoint)) {
                bestBreak = pos + br.length;
            }
        }
    }

    if (bestBreak > 0) splitAt = bestBreak;

    const part1 = narration.substring(0, splitAt).trim();
    const part2 = narration.substring(splitAt).trim();

    if (!part1 || !part2) {
        showToast('장면을 더 이상 분할할 수 없습니다.', 'error');
        return;
    }

    // Update existing scene
    scene.narration = part1;

    // Create new scene
    const newScene = {
        id: scene.id + 0.5,
        narration: part2,
        image_prompt: '',
        video_prompt: '',
        characters: [...(scene.characters || ['char_1'])],
        image_url: '',
        status: 'pending'
    };

    // Insert new scene after current
    AppState.scenes.splice(idx + 1, 0, newScene);

    // Re-number all scenes
    renumberScenes();
    renderScenes();
    showToast('장면이 분할되었습니다.', 'success');
}

function deleteScene(idx) {
    if (AppState.scenes.length <= 1) {
        showToast('최소 1개의 장면이 필요합니다.', 'error');
        return;
    }

    AppState.scenes.splice(idx, 1);
    renumberScenes();
    renderScenes();
    showToast('장면이 삭제되었습니다.', 'success');
}

function renumberScenes() {
    AppState.scenes.forEach((scene, i) => {
        scene.id = i + 1;
    });
}

// ============================================================
// Prompt Regeneration
// ============================================================

async function regeneratePrompt(idx, type) {
    const scene = AppState.scenes[idx];
    if (!scene) return;

    const style = document.getElementById('imageStyle')?.value || '';
    const charDesc = AppState.characters[AppState.activeCharacter]?.description || '';

    showToast(`장면 ${scene.id}의 ${type === 'image' ? '이미지' : '동영상'} 프롬프트 재생성 중...`, 'info');

    const result = await apiCall('/api/regenerate-prompt', {
        narration: scene.narration,
        scene_num: scene.id,
        prompt_type: type,
        style,
        character_desc: charDesc
    });

    if (result.success) {
        if (result.image_prompt) {
            scene.image_prompt = result.image_prompt;
        }
        if (result.video_prompt) {
            scene.video_prompt = result.video_prompt;
        }
        renderScenes();
        showToast('프롬프트가 재생성되었습니다.', 'success');
    }
}

// ============================================================
// Image Generation
// ============================================================

async function generateSingleImage(idx) {
    const scene = AppState.scenes[idx];
    if (!scene || !scene.image_prompt) {
        showToast('이미지 프롬프트가 비어있습니다.', 'error');
        return;
    }

    const style = document.getElementById('imageStyle')?.value || '';
    const model = document.getElementById('imageModel')?.value || '';
    const size = document.getElementById('imageSize')?.value || '';

    showToast(`장면 ${scene.id} 이미지 생성 중...`, 'info');

    const result = await apiCall('/api/generate-image', {
        prompt: scene.image_prompt,
        style,
        model,
        size
    });

    if (result.success) {
        scene.image_url = result.image_url;
        scene.status = 'completed';
        renderScenes();
        showToast(`장면 ${scene.id} 이미지가 생성되었습니다.`, 'success');
    }
}

async function batchGenerateImages() {
    if (AppState.scenes.length === 0) {
        showToast('생성할 장면이 없습니다.', 'error');
        return;
    }

    const style = document.getElementById('imageStyle')?.value || '';
    const model = document.getElementById('imageModel')?.value || '';
    const size = document.getElementById('imageSize')?.value || '';

    AppState.isGenerating = true;
    updateGenerationUI(true);

    const total = AppState.scenes.length;
    showProgress(0, total);

    // Generate images one by one for progress tracking
    for (let i = 0; i < AppState.scenes.length; i++) {
        if (!AppState.isGenerating) break;

        const scene = AppState.scenes[i];
        if (!scene.image_prompt) {
            showProgress(i + 1, total);
            continue;
        }

        // Skip scenes that already have images
        if (scene.image_url && !scene.image_url.includes('placeholder')) {
            showProgress(i + 1, total);
            continue;
        }

        const result = await apiCall('/api/generate-image', {
            prompt: scene.image_prompt,
            style,
            model,
            size
        });

        if (result.success) {
            scene.image_url = result.image_url;
            scene.status = 'completed';
        }

        showProgress(i + 1, total);
        renderScenes();
    }

    AppState.isGenerating = false;
    updateGenerationUI(false);
    showToast('이미지 일괄생성이 완료되었습니다.', 'success');
}

function showProgress(completed, total) {
    const container = document.getElementById('progressContainer');
    const text = document.getElementById('progressText');
    const fill = document.getElementById('progressFill');

    container.style.display = 'block';
    const percent = total > 0 ? (completed / total * 100) : 0;
    text.textContent = `영상 생성 중... (${completed}/${total})`;
    fill.style.width = `${percent}%`;

    if (completed >= total) {
        setTimeout(() => {
            container.style.display = 'none';
        }, 2000);
    }
}

function updateGenerationUI(isGenerating) {
    document.getElementById('btnBatchGenerate').disabled = isGenerating;
    document.getElementById('btnStopGeneration').disabled = !isGenerating;
}

// ============================================================
// Style Options
// ============================================================

function initStyleOptions() {
    const styleSelect = document.getElementById('imageStyle');
    const customStyle = document.getElementById('customStyle');

    styleSelect.addEventListener('change', () => {
        if (styleSelect.value === '') {
            customStyle.style.display = 'block';
        } else {
            customStyle.style.display = 'none';
        }
    });

    // Character buttons
    document.querySelectorAll('.btn-char').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.btn-char').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            AppState.activeCharacter = btn.dataset.char;
        });

        // Double-click to edit character
        btn.addEventListener('dblclick', () => {
            const charId = btn.dataset.char;
            openCharacterModal(charId);
        });
    });
}

// ============================================================
// Character Modal
// ============================================================

function openCharacterModal(charId) {
    const char = AppState.characters[charId] || { name: charId, description: '' };
    document.getElementById('charName').value = char.name;
    document.getElementById('charDescription').value = char.description;
    document.getElementById('characterModal').style.display = 'flex';
    document.getElementById('characterModal').dataset.charId = charId;
}

function initCharacterModal() {
    document.getElementById('btnCloseCharacter').addEventListener('click', () => {
        document.getElementById('characterModal').style.display = 'none';
    });

    document.getElementById('btnSaveCharacter').addEventListener('click', () => {
        const charId = document.getElementById('characterModal').dataset.charId;
        const name = document.getElementById('charName').value.trim();
        const desc = document.getElementById('charDescription').value.trim();

        AppState.characters[charId] = { name: name || charId, description: desc };
        document.getElementById('characterModal').style.display = 'none';
        showToast(`캐릭터 "${name || charId}"가 저장되었습니다.`, 'success');
    });
}

// ============================================================
// Settings Modal
// ============================================================

function initSettingsModal() {
    document.getElementById('btnSettings').addEventListener('click', () => {
        document.getElementById('settingsModal').style.display = 'flex';
        loadSettings();
    });

    document.getElementById('btnCloseSettings').addEventListener('click', () => {
        document.getElementById('settingsModal').style.display = 'none';
    });

    document.getElementById('btnSaveSettings').addEventListener('click', async () => {
        const openaiKey = document.getElementById('settingOpenaiKey').value.trim();
        const nanoBananaKey = document.getElementById('settingNanoBananaKey').value.trim();
        const nanoBananaUrl = document.getElementById('settingNanoBananaUrl').value.trim();

        const result = await apiCall('/api/settings', {
            openai_api_key: openaiKey,
            nanobanana_api_key: nanoBananaKey,
            nanobanana_api_url: nanoBananaUrl
        });

        if (result.success) {
            document.getElementById('settingsModal').style.display = 'none';
            showToast('설정이 저장되었습니다.', 'success');
        }
    });

    // Close modals on overlay click
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.style.display = 'none';
            }
        });
    });
}

async function loadSettings() {
    const result = await apiCall('/api/settings');
    if (result.success) {
        // Just show status, don't expose keys
        if (result.has_openai_key) {
            document.getElementById('settingOpenaiKey').placeholder = '키가 설정됨';
        }
        if (result.has_nanobanana_key) {
            document.getElementById('settingNanoBananaKey').placeholder = '키가 설정됨';
        }
        if (result.nanobanana_url) {
            document.getElementById('settingNanoBananaUrl').value = result.nanobanana_url;
        }
    }
}

// ============================================================
// Project Save/Load
// ============================================================

function initProjectActions() {
    document.getElementById('btnSaveProject').addEventListener('click', saveProject);

    document.getElementById('btnSaveLoad').addEventListener('click', saveProject);

    document.getElementById('projectName').addEventListener('change', (e) => {
        AppState.projectName = e.target.value;
    });
}

async function saveProject() {
    const name = document.getElementById('projectName').value.trim() || '새 프로젝트';

    const data = {
        scenes: AppState.scenes,
        characters: AppState.characters,
        script: document.getElementById('scriptEditor').value,
        style: document.getElementById('imageStyle')?.value || '',
        model: document.getElementById('imageModel')?.value || '',
        size: document.getElementById('imageSize')?.value || ''
    };

    const result = await apiCall('/api/save-project', { name, data });
    if (result.success) {
        showToast(result.message, 'success');
    }
}

// ============================================================
// Toolbar Actions
// ============================================================

function initToolbarActions() {
    // Run Analysis button in scenes tab
    document.getElementById('btnRunAnalysis').addEventListener('click', () => {
        const script = document.getElementById('scriptEditor').value.trim();
        if (!script) {
            showToast('먼저 "1. 대본" 탭에서 대본을 입력해주세요.', 'error');
            switchTab('script');
            return;
        }
        analyzeScript();
    });

    // Stop generation
    document.getElementById('btnStopGeneration').addEventListener('click', async () => {
        AppState.isGenerating = false;
        await apiCall('/api/stop-generation', {});
        updateGenerationUI(false);
        showToast('생성이 중지되었습니다.', 'info');
    });

    // Batch generate
    document.getElementById('btnBatchGenerate').addEventListener('click', () => {
        batchGenerateImages();
    });
}

// ============================================================
// Keyboard Shortcuts
// ============================================================

function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+S: Save project
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            saveProject();
        }

        // Ctrl+Enter: Analyze script (when in script tab)
        if (e.ctrlKey && e.key === 'Enter' && AppState.currentTab === 'script') {
            e.preventDefault();
            analyzeScript();
        }

        // Escape: Close modals
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay').forEach(m => {
                m.style.display = 'none';
            });
        }
    });
}

// ============================================================
// Initialize Application
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initScriptEditor();
    initStyleOptions();
    initSettingsModal();
    initCharacterModal();
    initProjectActions();
    initToolbarActions();
    initKeyboardShortcuts();

    // Set initial stats
    updateScriptStats();
});
