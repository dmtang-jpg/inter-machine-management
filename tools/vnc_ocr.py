#!/usr/bin/env python3
"""
Enhanced VNC screenshot OCR pipeline.
Preprocesses low-quality VNC screenshots for better Tesseract recognition.

Usage:
    python3 vnc_ocr.py screenshot.png
    python3 vnc_ocr.py screenshot.png --lang chi_sim+eng
"""

import sys
import argparse
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import numpy as np

def preprocess_vnc_screenshot(img, scale=3, contrast=2.0, sharpen=1.5):
    """
    Aggressive preprocessing for low-res VNC screenshots.
    
    Steps:
    1. Upscale (LANCZOS) — gives Tesseract more pixels to work with
    2. Grayscale — removes color noise from BGRX conversion artifacts
    3. Contrast enhancement — makes text pop from background
    4. Sharpen — recovers edge detail lost in upscale
    5. Adaptive threshold — binarize for clean OCR input
    """
    # Step 1: Upscale
    w, h = img.size
    img_large = img.resize((w * scale, h * scale), Image.Resampling.LANCZOS)
    
    # Step 2: Convert to grayscale
    img_gray = img_large.convert('L')
    
    # Step 3: Enhance contrast
    enhancer = ImageEnhance.Contrast(img_gray)
    img_contrast = enhancer.enhance(contrast)
    
    # Step 4: Sharpen
    enhancer_sharp = ImageEnhance.Sharpness(img_contrast)
    img_sharp = enhancer_sharp.enhance(sharpen)
    
    # Step 5: Brightness normalization (help with VNC dark areas)
    enhancer_bright = ImageEnhance.Brightness(img_sharp)
    img_bright = enhancer_bright.enhance(1.2)
    
    return img_bright

def ocr_screenshot(img_path, lang='chi_sim+eng', scale=3, contrast=2.0):
    """
    Full OCR pipeline for VNC screenshot.
    """
    img = Image.open(img_path)
    
    # Preprocess
    processed = preprocess_vnc_screenshot(img, scale=scale, contrast=contrast)
    
    # OCR with optimized config
    custom_config = '--psm 6'
    
    text = pytesseract.image_to_string(processed, lang=lang, config=custom_config)
    
    return text.strip()

def main():
    parser = argparse.ArgumentParser(description='Enhanced OCR for VNC screenshots')
    parser.add_argument('image', help='Path to screenshot image')
    parser.add_argument('--lang', default='chi_sim+eng', help='Tesseract language(s)')
    parser.add_argument('--scale', type=int, default=3, help='Upscale factor (default: 3)')
    parser.add_argument('--contrast', type=float, default=2.0, help='Contrast enhancement (default: 2.0)')
    args = parser.parse_args()
    
    text = ocr_screenshot(args.image, lang=args.lang, scale=args.scale, contrast=args.contrast)
    print(text)

if __name__ == '__main__':
    main()
