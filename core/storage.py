import cloudinary
import cloudinary.uploader
import cloudinary.utils
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class CloudinaryStorage(Storage):
    """Stores uploaded images on Cloudinary (reads CLOUDINARY_URL from the environment).
    The database keeps the Cloudinary public id; `.url` returns an optimised HTTPS delivery URL."""

    def _save(self, name, content):
        folder, _, fname = name.rpartition("/")
        content.seek(0)
        res = cloudinary.uploader.upload(
            content, folder=folder or None, public_id=fname.rsplit(".", 1)[0],
            resource_type="image", overwrite=False, unique_filename=False)
        return res["public_id"]

    def exists(self, name):
        return False  # public ids are unique (random file names are generated before saving)

    def url(self, name):
        return cloudinary.utils.cloudinary_url(name, secure=True, fetch_format="auto", quality="auto")[0]

    def delete(self, name):
        try:
            cloudinary.uploader.destroy(name, invalidate=True)
        except Exception:
            pass

    def size(self, name):
        return 0

    def _open(self, name, mode="rb"):
        raise NotImplementedError("Cloudinary files are delivered by URL, not opened locally.")
