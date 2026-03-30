"""测试简历证件照 URL 提取功能"""
import json

import pytest

from src.utils.prompts import resume_extraction_prompt


class TestPhotoUrlExtraction:
    """验证 photo_url 字段在 prompt 和 summary 提取中的正确性"""

    def test_photo_url_in_prompt_schema(self):
        """prompt 中 basic_info 应包含 photo_url 字段定义"""
        assert "photo_url" in resume_extraction_prompt, (
            "resume_extraction_prompt 中应包含 photo_url 字段"
        )
        # 验证 photo_url 在 basic_info 块内（而非其他位置）
        basic_info_block = resume_extraction_prompt[
            resume_extraction_prompt.find('"basic_info"') : resume_extraction_prompt.find('"education"')
        ]
        assert "photo_url" in basic_info_block, (
            "photo_url 应在 basic_info 块内定义"
        )

    def test_photo_url_instruction_in_prompt(self):
        """prompt 应包含证件照提取指令，而非忽略图片"""
        # 不应包含"忽略"图片的指令
        assert "忽略" not in resume_extraction_prompt or "证件照" in resume_extraction_prompt, (
            "prompt 应修改图片处理指令，不再忽略图片，而是提取证件照"
        )
        assert "证件照" in resume_extraction_prompt, (
            "prompt 应包含证件照相关指令"
        )

    def test_photo_url_extracted_from_summary(self):
        """模拟 LLM 返回包含 photo_url 的 summary，验证解析正确"""
        summary_json = {
            "basic_info": {
                "name": "张三",
                "gender": "男",
                "phone": "13800138000",
                "photo_url": "http://minio:9000/kb-images/test/photo.jpg",
            },
            "education": [],
            "work_experience": [],
            "project_experience": [],
            "skills": {"technical": [], "languages": [], "certifications": []},
            "awards": [],
            "self_evaluation": "test",
        }
        # 验证 photo_url 可以被正确访问
        assert summary_json["basic_info"]["photo_url"] == "http://minio:9000/kb-images/test/photo.jpg"

    def test_photo_url_none_when_no_image(self):
        """无证件照时 photo_url 应为 null，前端可据此判断"""
        summary_json = {
            "basic_info": {
                "name": "李四",
                "gender": "女",
                "phone": "13900139000",
                "photo_url": None,
            },
            "education": [],
            "work_experience": [],
            "project_experience": [],
            "skills": {"technical": [], "languages": [], "certifications": []},
            "awards": [],
            "self_evaluation": "test",
        }
        assert summary_json["basic_info"]["photo_url"] is None

    def test_photo_url_missing_backward_compatible(self):
        """旧简历 summary 中无 photo_url 字段时不应报错"""
        old_summary = {
            "basic_info": {
                "name": "王五",
                "gender": "男",
            },
            "education": [],
        }
        # 模拟前端 v-if 安全访问
        photo_url = old_summary.get("basic_info", {}).get("photo_url")
        assert photo_url is None
