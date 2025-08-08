#
# Copyright (c) 2025 broomd0g <broomd0g@wreckinglabs.org>
#
# This software is released under the MIT License.
# See the LICENSE file for more details.

import atexit
import shutil
import tempfile
from pathlib import Path


def cleanup():
    shutil.rmtree(TMP_DIR)


TMP_DIR = Path(tempfile.mkdtemp())
atexit.register(cleanup)
