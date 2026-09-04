"""Thin wrappers around each external engine.

An engine knows how to talk to one piece of machinery (ffmpeg, Pillow,
OpenCV, rembg, Upscayl, a hosted HTTP endpoint) and nothing about MCP,
CLI flags, or business rules. The tools layer composes them.
"""
