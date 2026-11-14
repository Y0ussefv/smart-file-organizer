"""
Tests for OpenAI precise titling (network mocked).
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src.core import openai_titler
from src.core.models import FileStatus, ScanConfig
from src.core.scanner import DirectoryScanner

pytestmark = pytest.mark.usefixtures("cloud_on")  # cloud paths, HTTP mocked; blocked by default


class FakeResp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        return self._body


def ok_answer(title, doc_type="Invoice", confidence="high"):
    return FakeResp(200, {"choices": [{"message": {"content": json.dumps(
        {"title": title, "document_type": doc_type, "confidence": confidence})}}]})


class TestGatherContent:
    def test_text_file_content_is_sent(self, tmp_path):
        f = tmp_path / "x.txt"
        f.write_text("INVOICE No 2026-0412\nDelfa SARL\nOffice supplies", encoding="utf-8")
        text, images = openai_titler.gather_file_content(f)
        assert "INVOICE No 2026-0412" in text and "Delfa SARL" in text
        assert images == []

    def test_image_is_sent_as_picture(self, tmp_path):
        f = tmp_path / "IMG_0001.png"
        Image.new("RGB", (40, 30), "red").save(f)
        text, images = openai_titler.gather_file_content(f)
        assert len(images) == 1 and images[0][1] == "image/jpeg"

    def test_unknown_binary_still_described(self, tmp_path):
        f = tmp_path / "blob.bin"
        f.write_bytes(b"\x00\x01\x02")
        text, _ = openai_titler.gather_file_content(f)
        assert "blob.bin" in text


class TestGenerateTitle:
    def test_returns_exact_title_and_strips_extension(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("Delfa invoice 2026-0412 for office supplies", encoding="utf-8")
        with patch.object(openai_titler.requests, "post", return_value=ok_answer("Delfa Invoice 2026-0412 Office Supplies.pdf")) as post:
            title, err, details = openai_titler.generate_precise_title(f, "sk-test", model="gpt-5-mini")
        assert err is None
        assert title == "Delfa Invoice 2026-0412 Office Supplies"
        assert details["confidence"] == "high"
        payload = post.call_args.kwargs["json"]
        assert payload["reasoning_effort"] == "low"
        assert payload["response_format"]["type"] == "json_schema"

    def test_non_reasoning_model_has_no_reasoning_effort(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("hello world content", encoding="utf-8")
        with patch.object(openai_titler.requests, "post", return_value=ok_answer("Hello World Note")) as post:
            openai_titler.generate_precise_title(f, "sk-test", model="gpt-4.1-mini")
        assert "reasoning_effort" not in post.call_args.kwargs["json"]

    def test_api_error_is_reported(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("content", encoding="utf-8")
        with patch.object(openai_titler.requests, "post",
                          return_value=FakeResp(401, {"error": {"message": "Incorrect API key"}})):
            title, err, _ = openai_titler.generate_precise_title(f, "sk-bad")
        assert title is None and "Incorrect API key" in err

    def test_no_key(self, tmp_path):
        title, err, _ = openai_titler.generate_precise_title(tmp_path / "x", "")
        assert title is None and err


class TestScannerUsesOpenAIForEveryFile:
    def test_every_file_gets_ai_title(self, tmp_path):
        (tmp_path / "scan001.txt").write_text("Contrat de travail - Ahmed Benali - Delfa", encoding="utf-8")
        (tmp_path / "data.bin").write_bytes(b"\x00\x01")  # normally kept unchanged
        answers = {
            "scan001.txt": ok_answer("Contrat De Travail Ahmed Benali Delfa", "Contract"),
            "data.bin": ok_answer("Delfa Binary Data Blob", "Binary"),
        }

        def fake_post(url, headers=None, json=None, timeout=None):
            text = json["messages"][1]["content"][0]["text"]
            for name, resp in answers.items():
                if f"Original filename: {name}" in text:
                    return resp
            raise AssertionError("unexpected file")

        cfg = ScanConfig(root_path=tmp_path, recursive=False, group_by_domain=False,
                         openai_api_key="sk-test", openai_model="gpt-5-mini")
        with patch.object(openai_titler.requests, "post", side_effect=fake_post):
            items, summary = DirectoryScanner(cfg).scan()

        names = {i.original_name: i for i in items}
        assert names["scan001.txt"].new_name == "Contrat_De_Travail_Ahmed_Benali_Delfa.txt"
        assert names["data.bin"].new_name == "Delfa_Binary_Data_Blob.bin"
        assert all(i.status == FileStatus.READY_TO_RENAME for i in items)
        assert "OpenAI" in names["scan001.txt"].explanation

    def test_falls_back_to_local_when_openai_fails(self, tmp_path):
        (tmp_path / "notes.md").write_text("# Quarterly Marketing Plan\n", encoding="utf-8")
        cfg = ScanConfig(root_path=tmp_path, recursive=False, group_by_domain=False, openai_api_key="sk-test")
        with patch.object(openai_titler.requests, "post",
                          return_value=FakeResp(500, {"error": {"message": "server down"}})):
            items, _ = DirectoryScanner(cfg).scan()
        assert items[0].new_name == "Quarterly_Marketing_Plan.md"
        assert "OpenAI unavailable" in items[0].explanation
