"""
Image Generator Service
- Handles image generation via NanoBanana Pro API
- Supports batch generation with progress tracking
- Configurable API endpoint for different providers
"""

import json
import os
import urllib.request
import urllib.error
import uuid
import time
import threading
from typing import Dict, Optional, Callable


class ImageGenerator:
    """Image generation service with NanoBanana Pro integration."""

    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        self.api_key = api_key or os.environ.get("NANOBANANA_API_KEY", "")
        self.api_url = api_url or os.environ.get(
            "NANOBANANA_API_URL",
            "https://api.nanobanana.pro/v1/generate"
        )
        self.generation_tasks = {}  # task_id -> status
        self._stop_flag = False

    def generate_image(self, prompt: str, style: str = "",
                       model: str = "nanobanana-pro-auto",
                       size: str = "기본 (복합 분할)",
                       negative_prompt: str = "") -> Dict:
        """
        Generate a single image from a prompt.
        Returns: { success, image_url, task_id, error }
        """
        task_id = str(uuid.uuid4())[:8]

        if not self.api_key:
            # Return placeholder when no API key configured
            return {
                'success': True,
                'image_url': f'/api/placeholder-image?prompt={urllib.request.quote(prompt[:100])}&id={task_id}',
                'task_id': task_id,
                'message': 'API 키가 설정되지 않아 플레이스홀더 이미지를 반환합니다.'
            }

        try:
            payload = json.dumps({
                "prompt": prompt,
                "style": style,
                "model": model,
                "size": size,
                "negative_prompt": negative_prompt
            }).encode('utf-8')

            req = urllib.request.Request(
                self.api_url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
            )

            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
                return {
                    'success': True,
                    'image_url': result.get('image_url', ''),
                    'task_id': task_id
                }

        except urllib.error.HTTPError as e:
            return {
                'success': False,
                'error': f'API 오류: {e.code} - {e.reason}',
                'task_id': task_id
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'이미지 생성 실패: {str(e)}',
                'task_id': task_id
            }

    def stop_generation(self):
        """Stop ongoing batch generation."""
        self._stop_flag = True

    def reset_stop_flag(self):
        """Reset the stop flag for new batch operations."""
        self._stop_flag = False

    def generate_batch(self, scenes: list, style: str = "",
                       model: str = "nanobanana-pro-auto",
                       size: str = "기본 (복합 분할)",
                       progress_callback: Optional[Callable] = None) -> Dict:
        """
        Generate images for multiple scenes.
        Returns: { success, results: [{ scene_id, image_url, error }], completed, total }
        """
        self.reset_stop_flag()
        batch_id = str(uuid.uuid4())[:8]
        results = []
        total = len(scenes)

        self.generation_tasks[batch_id] = {
            'status': 'running',
            'completed': 0,
            'total': total,
            'results': []
        }

        for i, scene in enumerate(scenes):
            if self._stop_flag:
                self.generation_tasks[batch_id]['status'] = 'stopped'
                break

            prompt = scene.get('image_prompt', '')
            if not prompt:
                results.append({
                    'scene_id': scene.get('id', i + 1),
                    'success': False,
                    'error': '이미지 프롬프트가 비어있습니다.'
                })
                continue

            result = self.generate_image(prompt, style, model, size)
            result['scene_id'] = scene.get('id', i + 1)
            results.append(result)

            self.generation_tasks[batch_id]['completed'] = i + 1
            self.generation_tasks[batch_id]['results'] = results

            if progress_callback:
                progress_callback(i + 1, total, result)

        if not self._stop_flag:
            self.generation_tasks[batch_id]['status'] = 'completed'

        return {
            'success': True,
            'batch_id': batch_id,
            'results': results,
            'completed': len(results),
            'total': total
        }

    def get_task_status(self, batch_id: str) -> Optional[Dict]:
        """Get the status of a batch generation task."""
        return self.generation_tasks.get(batch_id)
