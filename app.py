"""
Script-to-Video Generator Application
- Script analysis and scene splitting
- Image/motion prompt generation
- NanoBanana Pro image generation integration
- YouTube transcript extraction
"""

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
from services.script_analyzer import ScriptAnalyzer
from services.image_generator import ImageGenerator
import re
import os
import json
import threading

app = Flask(__name__)
CORS(app)

# Global instances
analyzer = ScriptAnalyzer()
image_gen = ImageGenerator()

# In-memory project storage
projects = {}
batch_status = {}

# -------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    """Get or update API settings."""
    if request.method == 'POST':
        data = request.get_json() or {}
        openai_key = data.get('openai_api_key', '')
        nanobanana_key = data.get('nanobanana_api_key', '')
        nanobanana_url = data.get('nanobanana_api_url', '')

        global analyzer, image_gen
        if openai_key:
            analyzer = ScriptAnalyzer(api_key=openai_key)
        if nanobanana_key or nanobanana_url:
            image_gen = ImageGenerator(
                api_key=nanobanana_key or image_gen.api_key,
                api_url=nanobanana_url or image_gen.api_url
            )

        return jsonify({'success': True, 'message': '설정이 저장되었습니다.'})

    return jsonify({
        'success': True,
        'has_openai_key': bool(analyzer.api_key),
        'has_nanobanana_key': bool(image_gen.api_key),
        'nanobanana_url': image_gen.api_url
    })

# -------------------------------------------------------------------
# Script Analysis
# -------------------------------------------------------------------

@app.route('/api/analyze-script', methods=['POST'])
def analyze_script():
    """Analyze a script and split into scenes with prompts."""
    data = request.get_json() or {}
    script = data.get('script', '')
    style = data.get('style', '')
    character_desc = data.get('character_desc', '')
    split_mode = data.get('split_mode', 'auto')

    if not script.strip():
        return jsonify({'success': False, 'error': '대본을 입력해주세요.'}), 400

    try:
        scenes = analyzer.analyze_script(script, style, character_desc, split_mode)
        return jsonify({
            'success': True,
            'scenes': scenes,
            'total': len(scenes)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/regenerate-prompt', methods=['POST'])
def regenerate_prompt():
    """Regenerate prompt(s) for a single scene."""
    data = request.get_json() or {}
    narration = data.get('narration', '')
    scene_num = data.get('scene_num', 1)
    prompt_type = data.get('prompt_type', 'both')
    style = data.get('style', '')
    character_desc = data.get('character_desc', '')

    if not narration.strip():
        return jsonify({'success': False, 'error': '나레이션을 입력해주세요.'}), 400

    try:
        result = analyzer.regenerate_prompt(
            narration, scene_num, prompt_type, style, character_desc
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# -------------------------------------------------------------------
# Image Generation
# -------------------------------------------------------------------

@app.route('/api/generate-image', methods=['POST'])
def generate_image():
    """Generate image for a single scene."""
    data = request.get_json() or {}
    prompt = data.get('prompt', '')
    style = data.get('style', '')
    model = data.get('model', 'nanobanana-pro-auto')
    size = data.get('size', '기본 (복합 분할)')

    if not prompt.strip():
        return jsonify({'success': False, 'error': '프롬프트를 입력해주세요.'}), 400

    try:
        result = image_gen.generate_image(prompt, style, model, size)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generate-images-batch', methods=['POST'])
def generate_images_batch():
    """Start batch image generation for multiple scenes."""
    data = request.get_json() or {}
    scenes = data.get('scenes', [])
    style = data.get('style', '')
    model = data.get('model', 'nanobanana-pro-auto')
    size = data.get('size', '기본 (복합 분할)')

    if not scenes:
        return jsonify({'success': False, 'error': '장면이 없습니다.'}), 400

    batch_id = None

    def run_batch():
        nonlocal batch_id
        result = image_gen.generate_batch(scenes, style, model, size)
        batch_id = result.get('batch_id')
        batch_status[batch_id] = result

    # Run synchronously for now (can be made async with threading)
    result = image_gen.generate_batch(scenes, style, model, size)
    return jsonify(result)


@app.route('/api/stop-generation', methods=['POST'])
def stop_generation():
    """Stop ongoing batch image generation."""
    image_gen.stop_generation()
    return jsonify({'success': True, 'message': '생성이 중지되었습니다.'})


@app.route('/api/placeholder-image')
def placeholder_image():
    """Generate a simple placeholder SVG image."""
    prompt = request.args.get('prompt', '이미지')
    img_id = request.args.get('id', '0')

    # Generate a color based on the id
    colors = ['#2d3436', '#636e72', '#2c3e50', '#34495e', '#1a1a2e', '#16213e']
    color = colors[hash(img_id) % len(colors)]

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
        <rect width="512" height="512" fill="{color}"/>
        <text x="256" y="240" text-anchor="middle" fill="#aaa" font-size="14" font-family="sans-serif">
            이미지 생성 대기중
        </text>
        <text x="256" y="270" text-anchor="middle" fill="#666" font-size="11" font-family="sans-serif">
            {prompt[:40]}
        </text>
    </svg>'''

    from flask import Response
    return Response(svg, mimetype='image/svg+xml')

# -------------------------------------------------------------------
# Project Save/Load
# -------------------------------------------------------------------

@app.route('/api/save-project', methods=['POST'])
def save_project():
    """Save project data."""
    data = request.get_json() or {}
    project_name = data.get('name', 'untitled')
    project_data = data.get('data', {})

    projects[project_name] = project_data
    return jsonify({'success': True, 'message': f'프로젝트 "{project_name}"이(가) 저장되었습니다.'})


@app.route('/api/load-project', methods=['POST'])
def load_project():
    """Load project data."""
    data = request.get_json() or {}
    project_name = data.get('name', '')

    if project_name in projects:
        return jsonify({'success': True, 'data': projects[project_name]})
    return jsonify({'success': False, 'error': '프로젝트를 찾을 수 없습니다.'}), 404


@app.route('/api/list-projects', methods=['GET'])
def list_projects():
    """List all saved projects."""
    return jsonify({'success': True, 'projects': list(projects.keys())})

# -------------------------------------------------------------------
# YouTube Transcript (existing)
# -------------------------------------------------------------------

def extract_video_id(url_or_id):
    if not url_or_id:
        return None
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return None


def get_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = None
        lang_used = None

        for lang in ['ko', 'en']:
            try:
                transcript = transcript_list.find_manually_created_transcript([lang])
                lang_used = lang
                break
            except NoTranscriptFound:
                try:
                    transcript = transcript_list.find_generated_transcript([lang])
                    lang_used = f"{lang}_auto"
                    break
                except NoTranscriptFound:
                    continue

        if not transcript:
            for t in transcript_list:
                transcript = t
                lang_used = t.language
                break

        if not transcript:
            return {'success': False, 'error': '자막 없음'}

        data = transcript.fetch()
        full_text = '\n'.join([item['text'] for item in data])

        return {
            'success': True,
            'transcript': full_text,
            'language': lang_used
        }

    except TranscriptsDisabled:
        return {'success': False, 'error': '자막이 비활성화된 영상입니다'}
    except VideoUnavailable:
        return {'success': False, 'error': '영상을 찾을 수 없습니다'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    return jsonify({'status': 'running', 'message': 'Script Video Generator 서버 작동 중'})


@app.route('/transcript', methods=['GET', 'POST'])
def get_video_transcript():
    if request.method == 'POST':
        data = request.get_json() or {}
        url_or_id = data.get('url', '') or data.get('video_id', '')
    else:
        url_or_id = request.args.get('url', '') or request.args.get('video_id', '')

    if not url_or_id:
        return jsonify({'success': False, 'error': 'URL 또는 Video ID를 입력해주세요'}), 400

    video_id = extract_video_id(url_or_id)
    if not video_id:
        return jsonify({'success': False, 'error': '올바른 YouTube URL이 아닙니다'}), 400

    result = get_transcript(video_id)
    result['video_id'] = video_id
    return jsonify(result)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
