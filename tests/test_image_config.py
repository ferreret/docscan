"""Tests para ImageConfig — modelo de configuración de imagen."""

from __future__ import annotations

import json

import pytest

from app.models.image_config import ImageConfig, parse_image_config, serialize_image_config


class TestImageConfigDefaults:
    def test_default_values(self):
        config = ImageConfig()
        assert config.format == "tiff"
        assert config.color_mode == "color"
        assert config.jpeg_quality == 85
        assert config.tiff_compression == "lzw"
        assert config.png_compression == 6
        assert config.bw_threshold == 128


class TestParseImageConfig:
    def test_parse_empty_string(self):
        config = parse_image_config("")
        assert config == ImageConfig()

    def test_parse_empty_json(self):
        config = parse_image_config("{}")
        assert config == ImageConfig()

    def test_parse_valid_json(self):
        data = json.dumps({
            "format": "jpg",
            "color_mode": "grayscale",
            "jpeg_quality": 50,
        })
        config = parse_image_config(data)
        assert config.format == "jpg"
        assert config.color_mode == "grayscale"
        assert config.jpeg_quality == 50
        # Los demás mantienen su valor por defecto
        assert config.tiff_compression == "lzw"
        assert config.png_compression == 6

    def test_parse_all_fields(self):
        data = json.dumps({
            "format": "png",
            "color_mode": "bw",
            "jpeg_quality": 10,
            "tiff_compression": "zip",
            "png_compression": 9,
            "bw_threshold": 200,
        })
        config = parse_image_config(data)
        assert config.format == "png"
        assert config.color_mode == "bw"
        assert config.jpeg_quality == 10
        assert config.tiff_compression == "zip"
        assert config.png_compression == 9
        assert config.bw_threshold == 200

    def test_parse_ignores_unknown_fields(self):
        data = json.dumps({
            "format": "jpg",
            "unknown_field": "valor",
            "another_unknown": 42,
        })
        config = parse_image_config(data)
        assert config.format == "jpg"
        assert not hasattr(config, "unknown_field")

    def test_parse_partial_fields(self):
        data = json.dumps({"jpeg_quality": 72})
        config = parse_image_config(data)
        assert config.jpeg_quality == 72
        assert config.format == "tiff"  # default

    def test_parse_ignores_legacy_dpi(self):
        """JSON antiguo con dpi se ignora sin error."""
        data = json.dumps({"format": "jpg", "dpi": 300})
        config = parse_image_config(data)
        assert config.format == "jpg"


class TestSerializeImageConfig:
    def test_serialize_defaults(self):
        config = ImageConfig()
        result = serialize_image_config(config)
        data = json.loads(result)
        assert data["format"] == "tiff"
        assert data["color_mode"] == "color"

    def test_serialize_custom_values(self):
        config = ImageConfig(format="jpg", jpeg_quality=50)
        result = serialize_image_config(config)
        data = json.loads(result)
        assert data["format"] == "jpg"
        assert data["jpeg_quality"] == 50

    def test_roundtrip(self):
        original = ImageConfig(
            format="png",
            color_mode="bw",
            jpeg_quality=10,
            tiff_compression="zip",
            png_compression=9,
            bw_threshold=200,
        )
        json_str = serialize_image_config(original)
        restored = parse_image_config(json_str)
        assert restored == original

    def test_roundtrip_defaults(self):
        original = ImageConfig()
        json_str = serialize_image_config(original)
        restored = parse_image_config(json_str)
        assert restored == original
