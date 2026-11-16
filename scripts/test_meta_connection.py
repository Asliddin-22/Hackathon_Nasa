#!/usr/bin/env python3
"""Safe connection smoke check. Default is mocked; --live is operator-only.

Never prints credentials, environment values, provider bodies, or exceptions.
Does not read .env files. Live mode sends only the synthetic fixture below.
"""
import argparse
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.services import meta_model

EVIDENCE = {'baseline': 'Synthetic reference: 65 bpm.',
            'current': 'Synthetic seven-day mean: 80 bpm. Cause unknown.'}


def mock_response(request, **kwargs):
    payload = json.loads(request.data)
    assert request.full_url == 'https://api.meta.ai/v1/responses'
    assert payload['model'] == 'muse-wonder-1.0'
    assert request.get_header('Authorization') == 'Bearer mock-credential-for-tests-only'
    return io.BytesIO(json.dumps({
        'status': 'completed', 'output': [
            {'type': 'reasoning', 'summary': []},
            {'type': 'message', 'role': 'assistant', 'status': 'completed', 'content': [{
                'type': 'output_text', 'text': '{"focus":["current"]}',
            }]},
        ],
    }).encode())


def check_connection(timeout):
    try:
        selected = meta_model.request_focus(EVIDENCE, timeout=timeout)
        if selected is None:
            return 'missing_credentials'
        # The same allowlist parser used by the backend already validated IDs.
        order = list(dict.fromkeys(selected + list(EVIDENCE)))
        return 'ok' if set(order) == set(EVIDENCE) else 'invalid_focus'
    except Exception as error:
        return meta_model.safe_failure_code(error)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true',
                        help='Explicitly call Meta; independent of the app ENABLE_LLM flag.')
    parser.add_argument('--timeout', type=int, default=60,
                        help='Connection/read timeout in seconds (1–120; default 60).')
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= 120:
        parser.error('Timeout must be between 1 and 120 seconds.')
    if args.live:
        # --live itself is operator opt-in. Do not silently skip this check when
        # the health application's remote-AI feature is disabled.
        code = check_connection(args.timeout)
    else:
        # Patch getters, not os.environ: existing secret values are untouched.
        with patch.object(meta_model, 'get_api_key', return_value='mock-credential-for-tests-only'), \
             patch.object(meta_model, 'open_response', side_effect=mock_response):
            code = check_connection(args.timeout)
    if code != 'ok':
        print(f'Connection not confirmed [{code}]. Offline monitoring remains available.')
        return 1
    print('PASS: ' + ('Live' if args.live else 'Mock') + ' Meta evidence-selection connection; all evidence retained.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
