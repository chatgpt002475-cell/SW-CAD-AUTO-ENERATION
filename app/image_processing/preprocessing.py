"""
Image Preprocessing Module
Handles image loading, channel normalization, background extraction, and filtering.
"""

import os
from typing import Tuple, Optional
import cv2
import numpy as np
from PIL import Image


class ImagePreprocessor:
    def __init__(self, contrast_factor: float = 1.0, blur_sigma: int = 7):
        self.contrast_factor = contrast_factor
        self.blur_sigma = blur_sigma

    def load_image(self, image_path: str) -> np.ndarray:
        """Loads image handling transparency and returns RGB array."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        pil_img = Image.open(image_path)
        if pil_img.mode in ('RGBA', 'LA') or (pil_img.mode == 'P' and 'transparency' in pil_img.info):
            bg = Image.new('RGB', pil_img.size, (255, 255, 255))
            if pil_img.mode != 'RGBA':
                pil_img = pil_img.convert('RGBA')
            bg.paste(pil_img, mask=pil_img.split()[-1])
            return np.array(bg)
        return np.array(pil_img.convert('RGB'))

    def preprocess(self, rgb_img: np.ndarray, invert: Optional[bool] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Processes RGB image to grayscale and binary mask with auto-polarity detection.
        Returns: (gray_image, binary_mask)
        """
        gray = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2GRAY)

        # Contrast adjustment
        if self.contrast_factor != 1.0:
            gray = cv2.convertScaleAbs(gray, alpha=self.contrast_factor, beta=0)

        # Edge-preserving smoothing
        smoothed = cv2.bilateralFilter(gray, d=self.blur_sigma, sigmaColor=75, sigmaSpace=75)

        # Otsu's thresholding
        _, thresh = cv2.threshold(smoothed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Border polarity check
        border = np.concatenate([thresh[0, :], thresh[-1, :], thresh[:, 0], thresh[:, -1]])
        is_light_bg = np.mean(border == 255) > 0.5

        if invert is True:
            mask = cv2.bitwise_not(thresh)
        elif invert is False:
            mask = thresh
        else:
            # Auto: make part interior white (255) on dark background (0)
            mask = cv2.bitwise_not(thresh) if is_light_bg else thresh

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        return gray, mask
