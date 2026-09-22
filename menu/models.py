# menu/models.py

from django.db import models
from shops.models import Shop

class MenuCategory(models.Model):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


import os
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image as PILImage

PILImage.MAX_IMAGE_PIXELS = None


class MenuItem(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="menu_items")
    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="menu_items/", blank=True, null=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Auto-optimize large 6-20MB PNG / JPEG images on upload
        if self.image and not getattr(self, '_image_optimized', False):
            try:
                if hasattr(self.image, 'file'):
                    if hasattr(self.image, 'seek'):
                        self.image.seek(0)
                    img = PILImage.open(self.image)
                    max_dim = 1200
                    needs_resize = img.width > max_dim or img.height > max_dim
                    needs_compression = getattr(self.image, 'size', 0) > 400 * 1024

                    if needs_resize or needs_compression:
                        if needs_resize:
                            img.thumbnail((max_dim, max_dim), PILImage.Resampling.LANCZOS)

                        output = BytesIO()
                        # Preserve alpha channel for transparent PNGs
                        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                            img.save(output, format='PNG', optimize=True, compress_level=6)
                            ext = '.png'
                        else:
                            if img.mode != 'RGB':
                                img = img.convert('RGB')
                            img.save(output, format='JPEG', quality=85, optimize=True)
                            ext = '.jpg'

                        base_name = os.path.splitext(os.path.basename(self.image.name))[0]
                        self.image.save(f"{base_name}{ext}", ContentFile(output.getvalue()), save=False)
                        self._image_optimized = True
            except Exception:
                pass
        super().save(*args, **kwargs)