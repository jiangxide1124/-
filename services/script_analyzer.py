"""
Script Analyzer Service
- Splits scripts into scenes
- Generates image prompts and video/motion prompts for each scene
- Supports AI-powered analysis (OpenAI API) and basic fallback
"""

import re
import json
import os
import urllib.request
import urllib.error
from typing import List, Dict, Optional


class ScriptAnalyzer:
    """Script analysis engine for splitting scripts into scenes and generating prompts."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    def split_scenes_by_paragraphs(self, script: str) -> List[str]:
        """Split script by double newlines (paragraph breaks)."""
        parts = re.split(r'\n\s*\n', script.strip())
        return [p.strip() for p in parts if p.strip()]

    def split_scenes_by_lines(self, script: str) -> List[str]:
        """Split script by single newlines."""
        parts = script.strip().split('\n')
        return [p.strip() for p in parts if p.strip()]

    def split_scenes_by_markers(self, script: str) -> List[str]:
        """Split script by explicit scene markers like [장면1], #장면, --- etc."""
        pattern = r'(?:^|\n)\s*(?:\[장면\s*\d*\]|#\s*장면|---+|===+)\s*\n?'
        parts = re.split(pattern, script.strip())
        return [p.strip() for p in parts if p.strip()]

    def detect_characters(self, text: str) -> List[str]:
        """Detect character references in text."""
        chars = set()
        # Pattern: (캐릭터명) or 캐릭터: 형태
        dialog_pattern = re.findall(r'[（(]([^)）]+)[)）]\s*[:：]', text)
        for c in dialog_pattern:
            chars.add(c.strip())
        colon_pattern = re.findall(r'^([가-힣a-zA-Z_]+\d*)\s*[:：]', text, re.MULTILINE)
        for c in colon_pattern:
            if len(c) <= 10:
                chars.add(c.strip())
        return list(chars) if chars else ['char_1']

    def build_scenes(self, parts: List[str]) -> List[Dict]:
        """Build scene objects from text parts."""
        scenes = []
        for i, part in enumerate(parts):
            characters = self.detect_characters(part)
            scene = {
                'id': i + 1,
                'narration': part,
                'image_prompt': '',
                'video_prompt': '',
                'characters': characters,
                'image_url': '',
                'status': 'pending'
            }
            scenes.append(scene)
        return scenes

    def generate_basic_image_prompt(self, narration: str, scene_num: int,
                                     style: str = "", character_desc: str = "") -> str:
        """Generate a basic image prompt from narration text (no AI)."""
        prompt_parts = []
        if style:
            prompt_parts.append(f"[{style}]")

        # Determine shot type based on text length
        if len(narration) < 30:
            prompt_parts.append("클로즈업 샷.")
        elif len(narration) < 80:
            prompt_parts.append("미디엄 샷.")
        else:
            prompt_parts.append("와이드 샷.")

        if character_desc:
            prompt_parts.append(character_desc)

        # Use narration as base description
        clean_narration = re.sub(r'[（(][^)）]*[)）]', '', narration)
        clean_narration = re.sub(r'^[가-힣a-zA-Z_]+\d*\s*[:：]\s*', '', clean_narration, flags=re.MULTILINE)
        prompt_parts.append(clean_narration.strip())
        prompt_parts.append("고해상도 이미지.")

        return ' '.join(prompt_parts)

    def generate_basic_video_prompt(self, narration: str, scene_num: int,
                                     style: str = "", character_desc: str = "") -> str:
        """Generate a basic video/motion prompt from narration text (no AI)."""
        prompt_parts = []
        if character_desc:
            prompt_parts.append(character_desc)

        clean_narration = re.sub(r'[（(][^)）]*[)）]', '', narration)
        clean_narration = re.sub(r'^[가-힣a-zA-Z_]+\d*\s*[:：]\s*', '', clean_narration, flags=re.MULTILINE)
        prompt_parts.append(clean_narration.strip())

        prompt_parts.append("카메라 느린 줌인.")
        prompt_parts.append("부드러운 움직임.")
        prompt_parts.append("고품질.")
        prompt_parts.append("No music. No background music.")

        return ' '.join(prompt_parts)

    def analyze_with_ai(self, script: str, style: str = "",
                        character_desc: str = "") -> Optional[List[Dict]]:
        """Use OpenAI API to analyze script and generate structured scene data."""
        if not self.api_key:
            return None

        system_prompt = """당신은 전문 영상 제작 AI 어시스턴트입니다.
사용자가 제공하는 대본을 분석하여 장면별로 나누고, 각 장면에 대해 이미지 생성 프롬프트와 영상(모션) 프롬프트를 생성합니다.

반드시 다음 JSON 형식으로 응답하세요:
{
  "scenes": [
    {
      "id": 1,
      "narration": "원본 나레이션 텍스트",
      "image_prompt": "상세한 이미지 생성 프롬프트 (카메라 앵글, 캐릭터 묘사, 배경, 분위기, 조명 포함)",
      "video_prompt": "상세한 영상/모션 프롬프트 (캐릭터 움직임, 카메라 움직임, 분위기, 오디오 설명 포함). 항상 'No music. No background music.' 으로 끝내세요.",
      "characters": ["등장 캐릭터 목록"]
    }
  ]
}

이미지 프롬프트 작성 규칙:
1. 카메라 앵글을 먼저 명시 (클로즈업, 미디엄 샷, 와이드 샷, 오버 더 숄더 등)
2. 캐릭터의 외형과 표정을 상세히 묘사
3. 배경과 환경을 구체적으로 설명
4. 분위기와 조명 스타일 명시
5. 고해상도, 시네마틱 품질 언급

영상/모션 프롬프트 작성 규칙:
1. 캐릭터의 구체적인 움직임 묘사
2. 카메라 워크 명시 (줌인, 줌아웃, 패닝, 틸트 등)
3. 전체적인 분위기와 톤
4. 움직임의 속도와 질감
5. 오디오/효과음 설명 (Audio: 형식으로)
6. 항상 'No music. No background music.'으로 끝내기"""

        user_prompt = f"대본을 분석해주세요:\n\n{script}"
        if style:
            user_prompt += f"\n\n스타일: {style}"
        if character_desc:
            user_prompt += f"\n\n캐릭터 설명: {character_desc}"

        try:
            payload = json.dumps({
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"}
            }).encode('utf-8')

            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
            )

            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result['choices'][0]['message']['content']
                data = json.loads(content)
                scenes = data.get('scenes', [])
                for i, scene in enumerate(scenes):
                    scene['id'] = i + 1
                    scene['image_url'] = ''
                    scene['status'] = 'pending'
                    if 'characters' not in scene:
                        scene['characters'] = ['char_1']
                return scenes

        except Exception as e:
            print(f"AI analysis failed: {e}")
            return None

    def analyze_script(self, script: str, style: str = "",
                       character_desc: str = "",
                       split_mode: str = "auto") -> List[Dict]:
        """
        Main entry point: analyze script and return structured scene data.
        split_mode: "auto" (paragraph breaks), "line" (every line), "marker" (explicit markers)
        """
        # Try AI analysis first
        ai_result = self.analyze_with_ai(script, style, character_desc)
        if ai_result:
            return ai_result

        # Fallback to rule-based analysis
        if split_mode == "line":
            parts = self.split_scenes_by_lines(script)
        elif split_mode == "marker":
            parts = self.split_scenes_by_markers(script)
        else:
            parts = self.split_scenes_by_paragraphs(script)

        scenes = self.build_scenes(parts)

        # Generate prompts for each scene
        for scene in scenes:
            scene['image_prompt'] = self.generate_basic_image_prompt(
                scene['narration'], scene['id'], style, character_desc
            )
            scene['video_prompt'] = self.generate_basic_video_prompt(
                scene['narration'], scene['id'], style, character_desc
            )

        return scenes

    def regenerate_prompt(self, narration: str, scene_num: int,
                          prompt_type: str = "both", style: str = "",
                          character_desc: str = "") -> Dict:
        """Regenerate prompt(s) for a single scene."""
        result = {}
        if prompt_type in ("both", "image"):
            if self.api_key:
                ai_result = self.analyze_with_ai(narration, style, character_desc)
                if ai_result and len(ai_result) > 0:
                    result['image_prompt'] = ai_result[0].get('image_prompt', '')
                else:
                    result['image_prompt'] = self.generate_basic_image_prompt(
                        narration, scene_num, style, character_desc
                    )
            else:
                result['image_prompt'] = self.generate_basic_image_prompt(
                    narration, scene_num, style, character_desc
                )

        if prompt_type in ("both", "video"):
            if self.api_key:
                ai_result = self.analyze_with_ai(narration, style, character_desc)
                if ai_result and len(ai_result) > 0:
                    result['video_prompt'] = ai_result[0].get('video_prompt', '')
                else:
                    result['video_prompt'] = self.generate_basic_video_prompt(
                        narration, scene_num, style, character_desc
                    )
            else:
                result['video_prompt'] = self.generate_basic_video_prompt(
                    narration, scene_num, style, character_desc
                )

        return result
