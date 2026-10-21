"""
Unit tests for Google AI Vision integration and image preparation.
"""

import io
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image

from src.core.ai_vision import (
    prepare_image_for_ai,
    analyze_image_with_google_ai,
    verify_google_api_key,
)
from src.core.content_extractors import ImageExtractor
from src.core.models import ScanConfig


class TestAIVision:

    def test_prepare_image_for_ai(self, tmp_path):
        img_path = tmp_path / "large_photo.png"
        img = Image.new("RGBA", (2000, 1500), color=(255, 0, 0, 128))
        img.save(str(img_path))

        jpeg_bytes, mime = prepare_image_for_ai(img_path, max_dimension=800)
        assert mime == "image/jpeg"
        assert len(jpeg_bytes) > 0

        # Verify resized dimensions
        decoded = Image.open(io.BytesIO(jpeg_bytes))
        w, h = decoded.size
        assert max(w, h) <= 800

    @patch("requests.post")
    def test_analyze_image_with_google_ai_success(self, mock_post, tmp_path):
        img_path = tmp_path / "sunset.jpg"
        img = Image.new("RGB", (100, 100), color="orange")
        img.save(str(img_path))

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Golden Hour Beach Sunset"}
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        title, err = analyze_image_with_google_ai(img_path, api_key="fake_key_123")
        assert err is None
        assert title == "Golden Hour Beach Sunset"

    @patch("requests.post")
    def test_analyze_image_error_handling(self, mock_post, tmp_path):
        img_path = tmp_path / "sample.jpg"
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(str(img_path))

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {
            "error": {"message": "API key not valid"}
        }
        mock_post.return_value = mock_resp

        title, err = analyze_image_with_google_ai(img_path, api_key="invalid_key")
        assert title is None
        assert "API key not valid" in err

    @patch("requests.post")
    def test_image_extractor_invokes_ai_when_enabled(self, mock_post, tmp_path):
        img_path = tmp_path / "diagram.png"
        img = Image.new("RGB", (100, 100), color="green")
        img.save(str(img_path))

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Cloud Architecture Diagram"}
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        config = ScanConfig(
            root_path=tmp_path,
            enable_google_ai=True,
            google_api_key="valid_test_key"
        )

        extractor = ImageExtractor()
        res = extractor.extract(img_path, config=config)

        assert res.title == "Cloud Architecture Diagram"
        assert "Google" in res.explanation

    @patch("requests.post")
    def test_verify_google_api_key_helper(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        valid, msg = verify_google_api_key("good_key")
        assert valid is True

        mock_resp.status_code = 403
        mock_resp.json.return_value = {"error": {"message": "Permission denied"}}
        valid2, msg2 = verify_google_api_key("bad_key")
        assert valid2 is False

    def test_detect_ai_provider(self):
        from src.core.ai_vision import detect_ai_provider
        assert detect_ai_provider("gsk_12345") == "groq"
        assert detect_ai_provider("AIzaSy12345") == "google"
        assert detect_ai_provider("custom_key", provider="groq") == "groq"
        assert detect_ai_provider("custom_key", provider="google") == "google"

    @patch("requests.post")
    def test_analyze_image_with_groq_success(self, mock_post, tmp_path):
        from src.core.ai_vision import analyze_image_with_groq
        img_path = tmp_path / "forest.jpg"
        img = Image.new("RGB", (100, 100), color="green")
        img.save(str(img_path))

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Pine Forest Mountain Trail"
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        title, err = analyze_image_with_groq(img_path, api_key="gsk_valid_key")
        assert err is None
        assert title == "Pine Forest Mountain Trail"

    @patch("requests.post")
    def test_verify_groq_api_key_helper(self, mock_post):
        from src.core.ai_vision import verify_groq_api_key
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        valid, msg = verify_groq_api_key("gsk_valid_key")
        assert valid is True
        assert "Groq Cloud" in msg

        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": {"message": "Invalid API Key"}}
        valid2, msg2 = verify_groq_api_key("gsk_invalid_key")
        assert valid2 is False

    @patch("requests.post")
    def test_image_extractor_with_groq_has_title_not_size(self, mock_post, tmp_path):
        """Verify image gets a descriptive title from Groq without dimensions/size."""
        from src.core.content_extractors import ImageExtractor

        img_path = tmp_path / "photo_sample.png"
        img = Image.new("RGB", (1920, 1080), color="blue")
        img.save(str(img_path))

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Company Headquarters Building"}}]
        }
        mock_post.return_value = mock_resp

        config = ScanConfig(
            root_path=tmp_path,
            groq_api_key="gsk_valid_key",
            enable_google_ai=True
        )

        extractor = ImageExtractor()
        res = extractor.extract(img_path, config=config)

        assert res.title == "Company Headquarters Building"
        assert "1920x1080" not in (res.title or "")
        assert "Groq Cloud" in res.explanation

    def test_image_fallback_never_uses_resolution_size(self, tmp_path):
        """Ensure unlabelled images are never named with resolution size (e.g. 1920x1080)."""
        from src.core.content_extractors import ImageExtractor

        img_path = tmp_path / "logo_delfa.png"
        img = Image.new("RGB", (1330, 1183), color="red")
        img.save(str(img_path))

        config = ScanConfig(root_path=tmp_path)
        extractor = ImageExtractor()
        res = extractor.extract(img_path, config=config)

        # Should derive title from clean stem and NEVER contain '1330x1183'
        assert "1330x1183" not in (res.title or "")
        assert res.title == "logo delfa" or "delfa" in (res.title or "").lower()

    @patch("requests.post")
    def test_pdf_extractor_invokes_groq_for_text(self, mock_post, tmp_path):
        """Verify PDF text is analyzed by Groq to derive document title."""
        from src.core.content_extractors import PDFExtractor

        pdf_path = tmp_path / "report_2026.pdf"
        # Create minimal PDF
        pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 0>>endobj\nxref\n0 3\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\ntrailer<</Size 3/Root 1 0 R>>\nstartxref\n102\n%%EOF\n")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Delfa Partnership Agreement"}}]
        }
        mock_post.return_value = mock_resp

        config = ScanConfig(
            root_path=tmp_path,
            groq_api_key="gsk_test_key",
            enable_google_ai=True
        )

        with patch("pypdf.PdfReader") as mock_reader_cls:
            mock_reader = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "This agreement is entered into by Delfa Corporation and its partners."
            mock_reader.pages = [mock_page]
            mock_reader.is_encrypted = False
            mock_reader.metadata = None
            mock_reader_cls.return_value = mock_reader

            extractor = PDFExtractor()
            res = extractor.extract(pdf_path, config=config)

            assert res.title == "Delfa Partnership Agreement"
            assert "Groq Cloud" in res.explanation

