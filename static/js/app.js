// 전역 변수
let currentAnalysisData = {
    single: null,
    multiple: null
};

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
    initializeTabs();
    initializeUrlInputs();
    initializeAnalyzeButtons();
    loadHistory();
});

// 탭 초기화
function initializeTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;

            // 모든 탭 버튼과 콘텐츠 비활성화
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            // 선택한 탭 활성화
            btn.classList.add('active');
            document.getElementById(`${tabName}-tab`).classList.add('active');
        });
    });
}

// URL 입력 초기화
function initializeUrlInputs() {
    const addUrlBtn = document.getElementById('add-url-btn');

    addUrlBtn.addEventListener('click', () => {
        const urlInputsDiv = document.getElementById('url-inputs');
        const currentInputs = urlInputsDiv.querySelectorAll('.url-input-row').length;

        if (currentInputs >= 3) {
            alert('최대 3개까지만 추가할 수 있습니다.');
            return;
        }

        const newRow = document.createElement('div');
        newRow.className = 'url-input-row';
        newRow.innerHTML = `
            <input type="text" class="url-input multiple-url" placeholder="https://www.youtube.com/watch?v=...">
            <button class="remove-btn" onclick="removeUrlInput(this)">×</button>
        `;

        urlInputsDiv.appendChild(newRow);

        // 3개가 되면 추가 버튼 비활성화
        if (currentInputs + 1 >= 3) {
            addUrlBtn.disabled = true;
        }
    });
}

// URL 입력 제거
function removeUrlInput(btn) {
    const urlInputsDiv = document.getElementById('url-inputs');
    const row = btn.parentElement;

    // 최소 1개는 남겨야 함
    if (urlInputsDiv.querySelectorAll('.url-input-row').length <= 1) {
        alert('최소 1개의 URL 입력창은 필요합니다.');
        return;
    }

    row.remove();

    // 추가 버튼 활성화
    document.getElementById('add-url-btn').disabled = false;
}

// 분석 버튼 초기화
function initializeAnalyzeButtons() {
    // 단일 영상 분석
    document.getElementById('single-analyze-btn').addEventListener('click', async () => {
        const url = document.getElementById('single-url').value.trim();

        if (!url) {
            alert('YouTube URL을 입력해주세요.');
            return;
        }

        await analyzeSingleVideo(url);
    });

    // 다중 영상 분석
    document.getElementById('multiple-analyze-btn').addEventListener('click', async () => {
        const urlInputs = document.querySelectorAll('.multiple-url');
        const urls = Array.from(urlInputs)
            .map(input => input.value.trim())
            .filter(url => url !== '');

        if (urls.length < 2) {
            alert('최소 2개 이상의 URL을 입력해주세요.');
            return;
        }

        await analyzeMultipleVideos(urls);
    });
}

// 단일 영상 분석
async function analyzeSingleVideo(url) {
    const loadingDiv = document.getElementById('single-loading');
    const loadingText = document.getElementById('single-loading-text');
    const resultDiv = document.getElementById('single-result');
    const analyzeBtn = document.getElementById('single-analyze-btn');

    // UI 초기화
    resultDiv.classList.add('hidden');
    loadingDiv.classList.remove('hidden');
    analyzeBtn.disabled = true;

    try {
        // 1단계: 자막 추출
        loadingText.textContent = '⏳ 1/2 자막 추출 중...';

        const response = await fetch('/analyze-single', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ video_url: url })
        });

        const result = await response.json();

        if (!result.success) {
            alert('❌ ' + result.error);
            return;
        }

        // 2단계: AI 분석 (이미 완료됨)
        loadingText.textContent = '⏳ 2/2 AI 분석 완료!';

        // 결과 저장
        currentAnalysisData.single = {
            url: url,
            title: result.video_title,
            transcript: result.transcript,
            insight: result.insight,
            timestamp: new Date().toISOString()
        };

        // 결과 표시
        document.getElementById('single-video-title').textContent = result.video_title;
        document.getElementById('single-insight').innerHTML = formatMarkdown(result.insight);
        document.getElementById('single-transcript').textContent = result.transcript;

        // 히스토리에 저장
        saveToHistory(currentAnalysisData.single, 'single');

        // UI 업데이트
        loadingDiv.classList.add('hidden');
        resultDiv.classList.remove('hidden');

    } catch (error) {
        alert('❌ 오류가 발생했습니다: ' + error.message);
    } finally {
        analyzeBtn.disabled = false;
    }
}

// 다중 영상 분석
async function analyzeMultipleVideos(urls) {
    const loadingDiv = document.getElementById('multiple-loading');
    const loadingText = document.getElementById('multiple-loading-text');
    const resultDiv = document.getElementById('multiple-result');
    const analyzeBtn = document.getElementById('multiple-analyze-btn');

    // UI 초기화
    resultDiv.classList.add('hidden');
    loadingDiv.classList.remove('hidden');
    analyzeBtn.disabled = true;

    try {
        // 1단계: 자막 추출
        loadingText.textContent = `⏳ 1/2 ${urls.length}개 영상의 자막 추출 중...`;

        const response = await fetch('/analyze-multiple', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ video_urls: urls })
        });

        const result = await response.json();

        if (!result.success) {
            alert('❌ ' + result.error);
            return;
        }

        // 2단계: AI 분석 (이미 완료됨)
        loadingText.textContent = '⏳ 2/2 통합 AI 분석 완료!';

        // 결과 저장
        currentAnalysisData.multiple = {
            videos: result.videos,
            insight: result.unified_insight,
            timestamp: new Date().toISOString()
        };

        // 통합 인사이트 표시
        document.getElementById('multiple-insight').innerHTML = formatMarkdown(result.unified_insight);

        // 각 영상 자막 표시
        const transcriptsDiv = document.getElementById('multiple-transcripts');
        transcriptsDiv.innerHTML = '';

        result.videos.forEach((video, index) => {
            const videoDiv = document.createElement('div');
            videoDiv.className = 'collapsible';
            videoDiv.innerHTML = `
                <div class="collapsible-header" onclick="toggleCollapse(this)">
                    <span>📄 영상 ${index + 1}: ${video.title}</span>
                    <div class="collapsible-actions">
                        <button class="download-btn" onclick="downloadTranscript('multiple', ${index}); event.stopPropagation();" title="다운로드">💾</button>
                        <span class="collapse-icon">▼</span>
                    </div>
                </div>
                <div class="collapsible-content collapsed">${video.transcript}</div>
            `;
            transcriptsDiv.appendChild(videoDiv);
        });

        // 히스토리에 저장
        saveToHistory(currentAnalysisData.multiple, 'multiple');

        // UI 업데이트
        loadingDiv.classList.add('hidden');
        resultDiv.classList.remove('hidden');

    } catch (error) {
        alert('❌ 오류가 발생했습니다: ' + error.message);
    } finally {
        analyzeBtn.disabled = false;
    }
}

// 접기/펼치기 토글
function toggleCollapse(header) {
    const content = header.nextElementSibling;
    const icon = header.querySelector('.collapse-icon');

    if (content.classList.contains('collapsed')) {
        content.classList.remove('collapsed');
        header.classList.remove('collapsed');
    } else {
        content.classList.add('collapsed');
        header.classList.add('collapsed');
    }
}

// 인사이트 복사
function copyInsight(type) {
    let text = '';

    if (type === 'single') {
        text = document.getElementById('single-insight').textContent;
    } else {
        text = document.getElementById('multiple-insight').textContent;
    }

    navigator.clipboard.writeText(text).then(() => {
        alert('✅ 인사이트가 클립보드에 복사되었습니다!');
    }).catch(err => {
        alert('❌ 복사 실패: ' + err);
    });
}

// 자막 다운로드
function downloadTranscript(type, index = null) {
    let text = '';
    let filename = '';

    if (type === 'single') {
        text = currentAnalysisData.single.transcript;
        filename = `${currentAnalysisData.single.title.replace(/[^a-zA-Z0-9가-힣]/g, '_')}_transcript.txt`;
    } else {
        const video = currentAnalysisData.multiple.videos[index];
        text = video.transcript;
        filename = `${video.title.replace(/[^a-zA-Z0-9가-힣]/g, '_')}_transcript.txt`;
    }

    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// 히스토리에 저장
function saveToHistory(data, type) {
    let history = JSON.parse(localStorage.getItem('analysisHistory') || '[]');

    const historyItem = {
        id: Date.now(),
        type: type,
        data: data,
        date: new Date().toLocaleString('ko-KR')
    };

    history.unshift(historyItem);

    // 최대 50개까지만 저장
    if (history.length > 50) {
        history = history.slice(0, 50);
    }

    localStorage.setItem('analysisHistory', JSON.stringify(history));
    loadHistory();
}

// 히스토리 로드
function loadHistory() {
    const history = JSON.parse(localStorage.getItem('analysisHistory') || '[]');
    const historyList = document.getElementById('history-list');

    if (history.length === 0) {
        historyList.innerHTML = '<div class="history-empty">분석 히스토리가 없습니다.</div>';
        return;
    }

    historyList.innerHTML = history.map(item => {
        const title = item.type === 'single' 
            ? item.data.title 
            : `${item.data.videos.length}개 영상 비교`;

        return `
            <div class="history-item">
                <div class="history-info">
                    <div class="history-date">${item.date}</div>
                    <div class="history-title">${title}</div>
                </div>
                <div class="history-actions">
                    <button class="history-view-btn" onclick="viewHistory(${item.id})">다시보기</button>
                    <button class="history-delete-btn" onclick="deleteHistory(${item.id})">×</button>
                </div>
            </div>
        `;
    }).join('');
}

// 히스토리 보기
function viewHistory(id) {
    const history = JSON.parse(localStorage.getItem('analysisHistory') || '[]');
    const item = history.find(h => h.id === id);

    if (!item) return;

    if (item.type === 'single') {
        // 단일 영상 탭으로 전환
        document.querySelector('[data-tab="single"]').click();

        currentAnalysisData.single = item.data;

        document.getElementById('single-url').value = item.data.url;
        document.getElementById('single-video-title').textContent = item.data.title;
        document.getElementById('single-insight').innerHTML = formatMarkdown(item.data.insight);
        document.getElementById('single-transcript').textContent = item.data.transcript;
        document.getElementById('single-result').classList.remove('hidden');

    } else {
        // 다중 영상 탭으로 전환
        document.querySelector('[data-tab="multiple"]').click();

        currentAnalysisData.multiple = item.data;

        document.getElementById('multiple-insight').innerHTML = formatMarkdown(item.data.insight);

        const transcriptsDiv = document.getElementById('multiple-transcripts');
        transcriptsDiv.innerHTML = '';

        item.data.videos.forEach((video, index) => {
            const videoDiv = document.createElement('div');
            videoDiv.className = 'collapsible';
            videoDiv.innerHTML = `
                <div class="collapsible-header" onclick="toggleCollapse(this)">
                    <span>📄 영상 ${index + 1}: ${video.title}</span>
                    <div class="collapsible-actions">
                        <button class="download-btn" onclick="downloadTranscript('multiple', ${index}); event.stopPropagation();" title="다운로드">💾</button>
                        <span class="collapse-icon">▼</span>
                    </div>
                </div>
                <div class="collapsible-content collapsed">${video.transcript}</div>
            `;
            transcriptsDiv.appendChild(videoDiv);
        });

        document.getElementById('multiple-result').classList.remove('hidden');
    }

    // 히스토리 섹션으로 스크롤
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// 히스토리 삭제
function deleteHistory(id) {
    if (!confirm('이 히스토리를 삭제하시겠습니까?')) return;

    let history = JSON.parse(localStorage.getItem('analysisHistory') || '[]');
    history = history.filter(h => h.id !== id);
    localStorage.setItem('analysisHistory', JSON.stringify(history));
    loadHistory();
}

// 전체 히스토리 삭제
function clearHistory() {
    if (!confirm('모든 히스토리를 삭제하시겠습니까?')) return;

    localStorage.removeItem('analysisHistory');
    loadHistory();
}

// 마크다운 간단 포맷팅
function formatMarkdown(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
}