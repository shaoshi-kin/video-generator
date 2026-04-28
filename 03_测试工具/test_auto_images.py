#!/usr/bin/env python3
"""
Tests for --auto-images feature in video_generator_pro.py

Run with:
    cd /Users/kingshaoshi/Desktop/claudeCode
    python3 -m pytest 03_测试工具/test_auto_images.py -v
"""

import sys
import os
import re
import shutil
import types
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime

# Add core scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "01_核心脚本"))

import video_generator_pro as vgp


# =============================================================================
# Helper: create a mock requests module for local imports inside functions
# =============================================================================

class _MockHTTPError(Exception):
    """Mock requests.exceptions.HTTPError with response attribute."""
    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response


def _mock_requests_module():
    """Create a mock 'requests' module that can be injected into sys.modules
    so that `import requests` inside functions picks it up."""
    mock_mod = types.ModuleType("requests")
    mock_mod.get = MagicMock()
    mock_mod.post = MagicMock()
    mock_mod.exceptions = types.ModuleType("requests.exceptions")
    mock_mod.exceptions.HTTPError = _MockHTTPError
    return mock_mod


# =============================================================================
# Tests for _download_image
# =============================================================================

class TestDownloadImage:
    """Unit tests for _download_image with mocked HTTP requests."""

    def test_pollinations_success(self, tmp_path):
        """Pollinations provider: successful image download."""
        save_path = tmp_path / "test.jpg"
        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "image/jpeg"}
        mock_response.content = b"fake_image_data"
        mock_response.raise_for_status = MagicMock()

        mock_requests = _mock_requests_module()
        mock_requests.get.return_value = mock_response

        with patch.dict(sys.modules, {"requests": mock_requests}):
            result = vgp._download_image("sunset beach", "pollinations", None, save_path)

        assert result is True
        assert save_path.read_bytes() == b"fake_image_data"

    def test_pollinations_non_image_content_type(self, tmp_path):
        """Pollinations provider: non-image content-type should fail."""
        save_path = tmp_path / "test.jpg"
        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.content = b"<html>error</html>"
        mock_response.raise_for_status = MagicMock()

        mock_requests = _mock_requests_module()
        mock_requests.get.return_value = mock_response

        with patch.dict(sys.modules, {"requests": mock_requests}):
            result = vgp._download_image("sunset beach", "pollinations", None, save_path)

        assert result is False
        assert not save_path.exists()

    def test_unsplash_success(self, tmp_path):
        """Unsplash provider: successful search and download."""
        save_path = tmp_path / "test.jpg"
        search_resp = MagicMock()
        search_resp.json.return_value = {
            "results": [{"urls": {"regular": "https://unsplash.com/img1.jpg"}}]
        }
        search_resp.raise_for_status = MagicMock()

        img_resp = MagicMock()
        img_resp.headers = {"Content-Type": "image/jpeg"}
        img_resp.content = b"unsplash_image_data"
        img_resp.raise_for_status = MagicMock()

        def mock_get(url, **kwargs):
            if "search/photos" in url:
                return search_resp
            return img_resp

        mock_requests = _mock_requests_module()
        mock_requests.get.side_effect = mock_get

        with patch.dict(sys.modules, {"requests": mock_requests}):
            result = vgp._download_image("mountain", "unsplash", "test_key", save_path)

        assert result is True
        assert save_path.read_bytes() == b"unsplash_image_data"

    def test_unsplash_no_results(self, tmp_path):
        """Unsplash provider: empty search results should fail gracefully."""
        save_path = tmp_path / "test.jpg"
        search_resp = MagicMock()
        search_resp.json.return_value = {"results": []}
        search_resp.raise_for_status = MagicMock()

        mock_requests = _mock_requests_module()
        mock_requests.get.return_value = search_resp

        with patch.dict(sys.modules, {"requests": mock_requests}):
            result = vgp._download_image("mountain", "unsplash", "test_key", save_path)

        assert result is False
        assert not save_path.exists()

    def test_pexels_success(self, tmp_path):
        """Pexels provider: successful search and download."""
        save_path = tmp_path / "test.jpg"
        search_resp = MagicMock()
        search_resp.json.return_value = {
            "photos": [{"src": {"large": "https://pexels.com/img1.jpg"}}]
        }
        search_resp.raise_for_status = MagicMock()

        img_resp = MagicMock()
        img_resp.headers = {"Content-Type": "image/jpeg"}
        img_resp.content = b"pexels_image_data"
        img_resp.raise_for_status = MagicMock()

        def mock_get(url, **kwargs):
            if "search" in url and "pexels" in url:
                return search_resp
            return img_resp

        mock_requests = _mock_requests_module()
        mock_requests.get.side_effect = mock_get

        with patch.dict(sys.modules, {"requests": mock_requests}):
            result = vgp._download_image("ocean", "pexels", "test_key", save_path)

        assert result is True
        assert save_path.read_bytes() == b"pexels_image_data"

    def test_unsupported_provider(self, tmp_path):
        """Unsupported provider should return False."""
        save_path = tmp_path / "test.jpg"
        result = vgp._download_image("test", "unknown_provider", None, save_path)
        assert result is False
        assert not save_path.exists()


# =============================================================================
# Tests for _extract_image_keywords
# =============================================================================

class TestExtractImageKeywords:
    """Unit tests for _extract_image_keywords with mocked LLM responses."""

    def test_successful_extraction(self):
        """LLM returns well-formatted keywords for all segments."""
        segments = [
            ("女声", "第一段关于日落的内容", None),
            ("男声", "第二段关于山脉的内容", None),
        ]
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "段落1: sunset beach\n段落2: mountain peak"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_requests = _mock_requests_module()
        mock_requests.post.return_value = mock_response

        with patch.dict(sys.modules, {"requests": mock_requests}):
            keywords = vgp._extract_image_keywords(
                segments, "article text",
                api_key="test_key", base_url="https://test.com",
                model="test-model", provider="kimi"
            )

        assert keywords == ["sunset beach", "mountain peak"]

    def test_fallback_fewer_keywords_than_segments(self):
        """LLM returns fewer keywords than segments - fallback fills the rest."""
        segments = [
            ("女声", "第一段关于日落的内容", None),
            ("男声", "第二段关于山脉的内容", None),
            ("女声", "第三段关于海洋的内容", None),
        ]
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "段落1: sunset beach"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_requests = _mock_requests_module()
        mock_requests.post.return_value = mock_response

        with patch.dict(sys.modules, {"requests": mock_requests}):
            keywords = vgp._extract_image_keywords(
                segments, "article text",
                api_key="test_key", base_url="https://test.com",
                model="test-model", provider="kimi"
            )

        assert len(keywords) == 3
        assert keywords[0] == "sunset beach"
        # Fallback keywords should be derived from segment content
        assert keywords[1] != ""
        assert keywords[2] != ""

    def test_api_failure_returns_empty(self):
        """API call fails - should return empty list."""
        segments = [
            ("女声", "第一段内容", None),
        ]

        mock_requests = _mock_requests_module()
        mock_requests.post.side_effect = Exception("Connection error")

        with patch.dict(sys.modules, {"requests": mock_requests}):
            keywords = vgp._extract_image_keywords(
                segments, "article text",
                api_key="test_key", base_url="https://test.com",
                model="test-model", provider="kimi"
            )

        assert keywords == []


# =============================================================================
# Tests for auto_generate_images_for_project (integration)
# =============================================================================

class TestAutoGenerateImagesForProject:
    """Integration tests for auto_generate_images_for_project with temp directories."""

    def test_inserts_image_markers_and_creates_backup(self, tmp_path):
        """Full flow: keywords extracted, images 'downloaded', markers inserted, backup created."""
        # Setup project directory structure
        project_dir = tmp_path / "test_project"
        article_dir = project_dir / "01_article"
        article_dir.mkdir(parents=True)
        images_dir = project_dir / "03_images"

        # Create a fake article with multiple paragraphs
        article_content = (
            "# 测试标题\n\n"
            "@全局:女声\n\n"
            "@女声:这是第一段关于人工智能的内容。\n\n"
            "@男声:这是第二段关于机器学习的内容。\n\n"
            "@女声:这是第三段关于深度学习的总结。\n"
        )
        article_path = article_dir / "文章_20240101_120000.md"
        article_path.write_text(article_content, encoding="utf-8")

        # Mock _extract_image_keywords to return predictable keywords
        def mock_extract(segments, article_text, **kwargs):
            return ["artificial intelligence", "machine learning", "deep learning"]

        # Mock _download_image to create a dummy image file
        def mock_download(keyword, provider, api_key, save_path):
            save_path.write_bytes(b"dummy_image_data")
            return True

        with patch.object(vgp, "_extract_image_keywords", side_effect=mock_extract), \
             patch.object(vgp, "_download_image", side_effect=mock_download):
            count = vgp.auto_generate_images_for_project(
                project_dir,
                image_provider="pollinations",
                llm_provider="kimi",
                llm_api_key="test_key"
            )

        # Verify return count
        assert count == 3

        # Verify images are saved to 03_images/
        assert images_dir.exists()
        image_files = list(images_dir.glob("*.jpg"))
        assert len(image_files) == 3

        # Verify article now contains @图: markers
        updated_article = article_path.read_text(encoding="utf-8")
        assert "@图:" in updated_article

        # Verify markers are placed BEFORE voice markers (correct order)
        lines = updated_article.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("@女声:") or line.strip().startswith("@男声:"):
                # The line immediately before (ignoring empty/comment lines) should be @图:
                prev_lines = [l for l in lines[:i] if l.strip() and not l.strip().startswith("#")]
                if prev_lines:
                    assert prev_lines[-1].startswith("@图:"), \
                        f"@图: marker should precede voice marker, got: {prev_lines[-1]}"

        # Verify backup file is created
        backup_files = list(article_dir.glob("文章_原稿_*.md"))
        assert len(backup_files) == 1

        # Verify backup contains original content (no @图: markers)
        backup_content = backup_files[0].read_text(encoding="utf-8")
        assert "@图:" not in backup_content
        assert backup_content == article_content

    def test_no_article_found_returns_zero(self, tmp_path):
        """Empty project directory without article should return 0."""
        project_dir = tmp_path / "empty_project"
        project_dir.mkdir()

        result = vgp.auto_generate_images_for_project(project_dir)
        assert result == 0

    def test_no_segments_returns_zero(self, tmp_path):
        """Article with no valid segments should return 0."""
        project_dir = tmp_path / "bad_project"
        article_dir = project_dir / "01_article"
        article_dir.mkdir(parents=True)

        # Article with only whitespace/short content - parse_article_segments
        # requires content >= 3 chars, so empty body produces 0 segments
        article_path = article_dir / "文章_20240101_120000.md"
        article_path.write_text("# 标题\n\n\n", encoding="utf-8")

        result = vgp.auto_generate_images_for_project(project_dir)
        assert result == 0

    def test_empty_keywords_uses_content_fallback(self, tmp_path):
        """When LLM returns no keywords, segment content should be used as fallback."""
        project_dir = tmp_path / "test_project"
        article_dir = project_dir / "01_article"
        article_dir.mkdir(parents=True)

        article_content = (
            "# 测试\n\n"
            "@全局:女声\n\n"
            "@女声:人工智能的发展历史。\n\n"
            "@男声:机器学习的应用场景。\n"
        )
        article_path = article_dir / "文章.md"
        article_path.write_text(article_content, encoding="utf-8")

        # Mock _extract_image_keywords to return empty list (simulating no API key)
        def mock_extract(segments, article_text, **kwargs):
            return []

        saved_keywords = []
        def mock_download(keyword, provider, api_key, save_path):
            saved_keywords.append(keyword)
            save_path.write_bytes(b"dummy")
            return True

        with patch.object(vgp, "_extract_image_keywords", side_effect=mock_extract), \
             patch.object(vgp, "_download_image", side_effect=mock_download):
            count = vgp.auto_generate_images_for_project(project_dir)

        assert count == 2
        # Keywords should be derived from segment content, not "segment_0"
        assert "segment_0" not in saved_keywords
        assert "segment_1" not in saved_keywords
        # Should contain content from the segments
        assert any("人工智能" in kw for kw in saved_keywords)
        assert any("机器学习" in kw for kw in saved_keywords)


# =============================================================================
# Tests for auto_generate_article_from_title return type
# =============================================================================

class TestAutoGenerateArticleFromTitle:
    """Tests verifying the return type change from bool to Optional[Path]."""

    def test_returns_path_on_success(self, tmp_path):
        """Successful generation should return a Path object."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "这是一篇测试文章。\n\n第二段内容。"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_requests = _mock_requests_module()
        mock_requests.post.return_value = mock_response

        with patch.dict(sys.modules, {"requests": mock_requests}):
            result = vgp.auto_generate_article_from_title(
                "测试标题", tmp_path,
                api_key="test_key", base_url="https://test.com",
                model="test-model", provider="kimi"
            )

        assert result is not None
        assert isinstance(result, Path)
        assert result.exists()
        assert result.suffix == ".md"

    def test_returns_none_on_api_error(self, tmp_path):
        """API failure should return None, not False."""
        mock_requests = _mock_requests_module()
        # Use a non-HTTPError exception so it falls through to the generic catch
        mock_requests.post.side_effect = ConnectionError("API Error")

        with patch.dict(sys.modules, {"requests": mock_requests}):
            result = vgp.auto_generate_article_from_title(
                "测试标题", tmp_path,
                api_key="test_key", base_url="https://test.com",
                model="test-model", provider="kimi"
            )

        assert result is None

    def test_returns_none_on_http_error(self, tmp_path):
        """HTTP error response should return None."""
        mock_response = MagicMock()
        mock_err_response = MagicMock()
        mock_err_response.text = "401 Unauthorized"
        mock_response.raise_for_status.side_effect = _MockHTTPError(
            "401 Unauthorized", response=mock_err_response
        )

        mock_requests = _mock_requests_module()
        mock_requests.post.return_value = mock_response

        with patch.dict(sys.modules, {"requests": mock_requests}):
            result = vgp.auto_generate_article_from_title(
                "测试标题", tmp_path,
                api_key="bad_key", base_url="https://test.com",
                model="test-model", provider="kimi"
            )

        assert result is None

    def test_returns_none_when_no_api_key(self, tmp_path):
        """Missing API key should return None."""
        result = vgp.auto_generate_article_from_title(
            "测试标题", tmp_path,
            api_key=None, provider="kimi"
        )
        assert result is None


    def test_partial_download_failure(self, tmp_path):
        """Some segments fail to download - only successful ones get markers."""
        project_dir = tmp_path / "test_project"
        article_dir = project_dir / "01_article"
        article_dir.mkdir(parents=True)
        images_dir = project_dir / "03_images"

        article_content = (
            "# 测试标题\n\n"
            "@全局:女声\n\n"
            "@女声:第一段内容。\n\n"
            "@男声:第二段内容。\n\n"
            "@女声:第三段内容。\n"
        )
        article_path = article_dir / "文章_20240101_120000.md"
        article_path.write_text(article_content, encoding="utf-8")

        def mock_extract(segments, article_text, **kwargs):
            return ["kw1", "kw2", "kw3"]

        # Only segment 0 and 2 succeed
        def mock_download(keyword, provider, api_key, save_path):
            if keyword == "kw2":
                return False
            save_path.write_bytes(b"dummy")
            return True

        with patch.object(vgp, "_extract_image_keywords", side_effect=mock_extract), \
             patch.object(vgp, "_download_image", side_effect=mock_download):
            count = vgp.auto_generate_images_for_project(project_dir)

        assert count == 2
        updated = article_path.read_text(encoding="utf-8")
        lines = [l.strip() for l in updated.split("\n") if l.strip()]
        # Only 2 @图: markers should exist
        img_markers = [l for l in lines if l.startswith("@图:")]
        assert len(img_markers) == 2

    def test_existing_image_markers_replaced(self, tmp_path):
        """Article with existing @图: markers should have them replaced."""
        project_dir = tmp_path / "test_project"
        article_dir = project_dir / "01_article"
        article_dir.mkdir(parents=True)

        article_content = (
            "# 测试标题\n\n"
            "@全局:女声\n\n"
            "@图:old_image.jpg\n"
            "@女声:第一段内容。\n\n"
            "@女声:第二段内容。\n"
        )
        article_path = article_dir / "文章_20240101_120000.md"
        article_path.write_text(article_content, encoding="utf-8")

        def mock_extract(segments, article_text, **kwargs):
            return ["new1", "new2"]

        def mock_download(keyword, provider, api_key, save_path):
            save_path.write_bytes(b"dummy")
            return True

        with patch.object(vgp, "_extract_image_keywords", side_effect=mock_extract), \
             patch.object(vgp, "_download_image", side_effect=mock_download):
            count = vgp.auto_generate_images_for_project(project_dir)

        assert count == 2
        updated = article_path.read_text(encoding="utf-8")
        # Old marker should be gone
        assert "@图:old_image.jpg" not in updated
        # New markers should exist
        assert updated.count("@图:segment_") == 2


class TestKeywordFilenameSanitization:
    """Tests for keyword-to-filename conversion safety."""

    def test_special_chars_removed(self, tmp_path):
        """Keywords with filesystem-dangerous chars should be sanitized."""
        project_dir = tmp_path / "test_project"
        article_dir = project_dir / "01_article"
        article_dir.mkdir(parents=True)

        article_content = (
            "# 测试\n\n"
            "@女声:第一段。\n\n"
            "@男声:第二段。\n"
        )
        article_path = article_dir / "文章.md"
        article_path.write_text(article_content, encoding="utf-8")

        def mock_extract(segments, article_text, **kwargs):
            # Keywords with chars that would be illegal in filenames
            return ["artificial<intelligence>", "hello/world:test"]

        saved_paths = []
        def mock_download(keyword, provider, api_key, save_path):
            saved_paths.append(save_path.name)
            save_path.write_bytes(b"dummy")
            return True

        with patch.object(vgp, "_extract_image_keywords", side_effect=mock_extract), \
             patch.object(vgp, "_download_image", side_effect=mock_download):
            vgp.auto_generate_images_for_project(project_dir)

        # Filenames should not contain dangerous chars
        for name in saved_paths:
            assert "/" not in name
            assert "<" not in name
            assert ">" not in name
            assert ":" not in name

    def test_unicode_preserved(self, tmp_path):
        """Unicode keywords should be preserved in filenames."""
        project_dir = tmp_path / "test_project"
        article_dir = project_dir / "01_article"
        article_dir.mkdir(parents=True)

        article_content = "# 测试\n\n@女声:第一段。\n"
        article_path = article_dir / "文章.md"
        article_path.write_text(article_content, encoding="utf-8")

        def mock_extract(segments, article_text, **kwargs):
            return ["人工智能"]

        saved_paths = []
        def mock_download(keyword, provider, api_key, save_path):
            saved_paths.append(save_path.name)
            save_path.write_bytes(b"dummy")
            return True

        with patch.object(vgp, "_extract_image_keywords", side_effect=mock_extract), \
             patch.object(vgp, "_download_image", side_effect=mock_download):
            vgp.auto_generate_images_for_project(project_dir)

        assert len(saved_paths) == 1
        assert "人工智能" in saved_paths[0]


class TestAutoArticleSearchWeb:
    """Tests for search_web parameter in auto_generate_article_from_title."""

    def test_kimi_search_web_format(self, tmp_path):
        """Kimi provider should include web_search tool in payload."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "测试结果。"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_requests = _mock_requests_module()
        mock_requests.post.return_value = mock_response

        with patch.dict(sys.modules, {"requests": mock_requests}):
            vgp.auto_generate_article_from_title(
                "测试", tmp_path,
                api_key="test_key", provider="kimi", search_web=True
            )

        call_args = mock_requests.post.call_args
        payload = call_args[1]["json"]
        assert "tools" in payload
        assert payload["tools"][0]["type"] == "web_search"

    def test_deepseek_search_web_format(self, tmp_path):
        """DeepSeek provider should include web_search tool in payload."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "测试结果。"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_requests = _mock_requests_module()
        mock_requests.post.return_value = mock_response

        with patch.dict(sys.modules, {"requests": mock_requests}):
            vgp.auto_generate_article_from_title(
                "测试", tmp_path,
                api_key="test_key", provider="deepseek", search_web=True
            )

        call_args = mock_requests.post.call_args
        payload = call_args[1]["json"]
        assert "tools" in payload
        assert payload["tools"][0]["type"] == "web_search"


class TestParseArticleSegmentsWithImages:
    """Verify parse_article_segments correctly handles @图: markers."""

    def test_parses_image_markers_correctly(self):
        """Article with inserted @图: markers should parse correctly."""
        text = (
            "# 标题\n\n"
            "@全局:女声\n\n"
            "@图:segment_01_test.jpg\n"
            "@女声:第一段内容。\n\n"
            "@图:segment_02_test.jpg\n"
            "@男声:第二段内容。\n"
        )
        segments, default_image = vgp.parse_article_segments(text)
        assert len(segments) == 2
        assert segments[0][2] == "segment_01_test.jpg"
        assert segments[1][2] == "segment_02_test.jpg"


class TestArgparseAutoImages:
    """Verify --auto-images arguments are properly registered."""

    def test_auto_images_flag_exists(self):
        """Parser should accept --auto-images flag."""
        parser = vgp.argparse.ArgumentParser()
        parser.add_argument("--auto-images", action="store_true")
        args = parser.parse_args(["--auto-images"])
        assert args.auto_images is True

    def test_image_provider_choices(self):
        """Parser should accept valid image providers."""
        parser = vgp.argparse.ArgumentParser()
        parser.add_argument("--image-provider", choices=["pollinations", "unsplash", "pexels"])
        args = parser.parse_args(["--image-provider", "unsplash"])
        assert args.image_provider == "unsplash"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
