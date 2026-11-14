"""Open a NISAR HDF5 file over HTTPS and read only the bytes needed.

NISAR GCOV files are ~6 GB, but our AOI is a small part of each scene.
h5py can read from any Python file object, so this module provides one that
fetches byte ranges on demand (with a small block cache).

Earthdata auth: the NISAR URL redirects (with our bearer token) to a short-lived
signed S3 URL; we resolve that once and range-read the signed URL directly.
"""

import io
import time
from collections import OrderedDict

import requests

from earthdata_auth import get_token

BLOCK = 4 * 1024 * 1024  # 4 MB blocks
MAX_BLOCKS = 64           # up to ~256 MB cache


def resolve_signed_url(url, token=None):
    """Follow the Earthdata redirect chain once and return the final (signed) URL + size."""
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {token or get_token()}"
    for attempt in range(5):  # NASA's gateway occasionally returns 5xx; back off and retry
        try:
            r = s.get(url, headers={"Range": "bytes=0-0"}, allow_redirects=True, timeout=120)
            if r.status_code in (200, 206):
                break
            if r.status_code < 500 or attempt == 4:
                raise RuntimeError(f"HTTP {r.status_code} resolving {url}: {r.text[:200]}")
        except requests.RequestException:
            if attempt == 4:
                raise
        time.sleep(10 * (attempt + 1))
    size = int(r.headers["Content-Range"].split("/")[-1]) if "Content-Range" in r.headers else None
    return r.url, size


class RangeFile(io.RawIOBase):
    def __init__(self, url, size, block=BLOCK):
        self.url, self.size, self.pos, self.block = url, size, 0, block
        self.cache = OrderedDict()
        self.http = requests.Session()
        self.bytes_fetched = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence]
        self.pos = base + offset
        return self.pos

    def _block(self, idx):
        if idx in self.cache:
            self.cache.move_to_end(idx)
            return self.cache[idx]
        start = idx * self.block
        end = min(start + self.block, self.size) - 1
        for attempt in range(8):  # rides out short network/DNS drops (~2.5 min total backoff)
            try:
                r = self.http.get(self.url, headers={"Range": f"bytes={start}-{end}"}, timeout=60)
                r.raise_for_status()
                break
            except requests.RequestException as e:
                if attempt == 7:
                    raise
                wait = min(5 * 2 ** attempt, 60)
                print(f"    network error ({type(e).__name__}), retrying in {wait}s…", flush=True)
                time.sleep(wait)
        data = r.content
        self.bytes_fetched += len(data)
        self.cache[idx] = data
        if len(self.cache) > MAX_BLOCKS:
            self.cache.popitem(last=False)
        return data

    def readinto(self, b):
        n = min(len(b), max(self.size - self.pos, 0))
        out, filled = memoryview(b), 0
        while filled < n:
            idx, off = divmod(self.pos + filled, self.block)
            chunk = self._block(idx)[off:off + n - filled]
            out[filled:filled + len(chunk)] = chunk
            filled += len(chunk)
        self.pos += filled
        return filled


def open_remote(url, token=None, block=BLOCK):
    """Return (file_object, size) for use with h5py.File(file_object, 'r').

    Smaller blocks (e.g. 1 MB) fetch less when only metadata + a small window is needed."""
    signed, size = resolve_signed_url(url, token)
    return RangeFile(signed, size, block), size
