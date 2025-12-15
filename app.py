from flask import Flask, request, jsonify
from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
import re

app = Flask(__name__)
CORS(app)

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
        
        # 한국어 우선
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
        
        # 아무 자막이나
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

@app.route('/')
def home():
    return jsonify({'status': 'running', 'message': 'YouTube 자막 서버 작동 중'})

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
    app.run(host='0.0.0.0', port=5000)
