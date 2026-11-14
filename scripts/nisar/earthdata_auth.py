"""Earthdata token handling for NISAR downloads, with no plain-text password files.

Uses an Earthdata *token* (generated at urs.earthdata.nasa.gov → Generate Token),
never your password. The token is kept in Windows Credential Manager via `keyring`.

    python scripts/nisar/earthdata_auth.py --save    # paste token (hidden), store it, test it
    python scripts/nisar/earthdata_auth.py --test    # test the stored token
    python scripts/nisar/earthdata_auth.py --forget  # delete it from Credential Manager

Other scripts call get_token(). Lookup order: EARTHDATA_TOKEN environment
variable → Credential Manager → hidden prompt (nothing stored).
"""

import argparse
import getpass
import os
import sys

import keyring
import requests

SERVICE = "coastlens-earthdata"
ACCOUNT = "token"
# Small real NISAR file over Keti Bandar (L3 soil moisture, ~85 MB). Only 8 bytes are requested.
TEST_URL = (
    "https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L3_SME2_PROVISIONAL_V1/"
    "NISAR_L3_PR_SME2_032_164_D_076_2005_QPDH_A_20261011T140554_20261011T140629_P05023_N_F_J_001/"
    "NISAR_L3_PR_SME2_032_164_D_076_2005_QPDH_A_20261011T140554_20261011T140629_P05023_N_F_J_001.h5"
)


def get_token(prompt_if_missing=True):
    token = os.environ.get("EARTHDATA_TOKEN") or keyring.get_password(SERVICE, ACCOUNT)
    if not token and prompt_if_missing:
        token = getpass.getpass("Paste Earthdata token (hidden, not stored): ").strip()
    return token or None


def session(token=None):
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {token or get_token()}"
    return s


def test(token):
    r = session(token).get(TEST_URL, headers={"Range": "bytes=0-7"}, timeout=60, allow_redirects=True)
    if r.status_code in (200, 206) and r.content[:4] == b"\x89HDF":
        print("OK - Token works: NISAR file reachable (read 8 bytes, HDF5 signature OK).")
        return True
    hint = {401: "token rejected (expired or mistyped?)",
            403: "access denied. Log in once at https://search.asf.alaska.edu and accept any agreement shown"}
    print(f"FAILED - Test failed: HTTP {r.status_code}: {hint.get(r.status_code, r.text[:200])}")
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--save", action="store_true", help="store a token in Windows Credential Manager and test it")
    g.add_argument("--test", action="store_true", help="test the stored token")
    g.add_argument("--forget", action="store_true", help="remove the stored token")
    args = ap.parse_args()

    if args.save:
        token = getpass.getpass("Paste your Earthdata token (input is hidden): ").strip()
        if not token:
            sys.exit("No token entered.")
        if test(token):
            keyring.set_password(SERVICE, ACCOUNT, token)
            print(f"Saved in Windows Credential Manager as '{SERVICE}'. You can delete it there any time.")
        else:
            sys.exit("Not saved.")
    elif args.test:
        token = get_token(prompt_if_missing=False)
        if not token:
            sys.exit("No stored token. Run with --save first.")
        sys.exit(0 if test(token) else 1)
    elif args.forget:
        try:
            keyring.delete_password(SERVICE, ACCOUNT)
            print("Token removed from Credential Manager.")
        except keyring.errors.PasswordDeleteError:
            print("No stored token found.")


if __name__ == "__main__":
    main()
