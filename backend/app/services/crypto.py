"""Encrypt event payloads in the simulated communications queue."""
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet
from ..config import ROOT


def cipher():
    key = os.getenv('SYNC_ENCRYPTION_KEY')
    if key:
        return Fernet(key.encode())
    path = ROOT / '.local' / 'sync.key'
    path.parent.mkdir(mode=0o700, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'wb') as output:
            output.write(Fernet.generate_key())
    return Fernet(path.read_bytes())


def encrypt(payload):
    return {'ciphertext': cipher().encrypt(json.dumps(payload).encode()).decode()}


def decrypt(payload):
    return json.loads(cipher().decrypt(payload['ciphertext'].encode()))
