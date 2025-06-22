import json
import os
from typing import Dict, List, Optional
from pathlib import Path


class ContentLoader:
    def __init__(self):
        self.base_path = Path(__file__).parent / "courses"

    def load_course(
        self, age_group: str, subject: str, course_name: str
    ) -> Optional[Dict]:
        """Load a course from JSON file"""
        file_path = self.base_path / age_group / subject / f"{course_name}.json"

        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def list_courses(self, age_group: str, subject: str) -> List[str]:
        """List all courses for age group and subject"""
        folder_path = self.base_path / age_group / subject
        if folder_path.exists():
            return [f.stem for f in folder_path.glob("*.json")]
        return []


content_loader = ContentLoader()
