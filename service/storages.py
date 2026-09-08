import sys

from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage


class CloudinaryCatalogStorage(Storage):
    def _save(self, name, content):
        from cloudinary.uploader import upload

        result = upload(
            content,
            folder=settings.CLOUDINARY_CATALOG_FOLDER,
            resource_type="image",
            unique_filename=True,
            overwrite=False,
        )
        return result["public_id"]

    def exists(self, name):
        return False

    def url(self, name):
        from cloudinary import CloudinaryImage

        return CloudinaryImage(name).build_url(secure=True)

    def delete(self, name):
        if not name:
            return

        from cloudinary.uploader import destroy

        destroy(name, resource_type="image", invalidate=True)


def catalog_image_storage():
    if getattr(settings, "CLOUDINARY_URL", "") and "test" not in sys.argv:
        return CloudinaryCatalogStorage()

    return FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)
