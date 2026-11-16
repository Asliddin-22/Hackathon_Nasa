"""Mock-only Meta integration tests: no key files or real provider calls."""
import io
import json
import urllib.error
import urllib.request
from unittest.mock import Mock

import pytest

from backend.app.services import meta_model
from backend.app.services.ai_assistant import select_evidence

MOCK_KEY = 'mock-credential-for-tests-only'
EVIDENCE = {'baseline': 'Synthetic reference: 65 bpm.', 'current': 'Synthetic mean: 80 bpm.'}
REAL_GET_API_KEY = meta_model.get_api_key


def response(focus=None, **changes):
    body = {'status': 'completed', 'output': [{'type': 'message', 'content': [{
        'type': 'output_text', 'text': json.dumps({'focus': ['current'] if focus is None else focus}),
    }]}], **changes}
    return io.BytesIO(json.dumps(body).encode())


@pytest.fixture(autouse=True)
def isolated_provider(monkeypatch):
    # Never inspect or depend on credentials in the test runner's environment.
    monkeypatch.setattr('backend.app.services.ai_assistant.llm_enabled', lambda: True)
    monkeypatch.setattr(meta_model, 'get_api_key', lambda: MOCK_KEY)
    def unexpected_network(*args, **kwargs):
        pytest.fail('A test attempted an unmocked provider call')
    original_open = meta_model.open_response
    monkeypatch.setattr(meta_model, 'open_response', unexpected_network)
    return original_open


def test_credential_binding_uses_only_model_api_key(monkeypatch):
    def getenv(name, default):
        assert name == 'MODEL_API_KEY' and default == ''
        return MOCK_KEY
    monkeypatch.setattr(meta_model.os, 'getenv', getenv)
    assert REAL_GET_API_KEY() == MOCK_KEY


def test_mock_connection_request_and_response(monkeypatch):
    def connect(request, **kwargs):
        assert request.full_url == 'https://api.meta.ai/v1/responses'
        assert request.method == 'POST'
        assert request.get_header('Authorization') == f'Bearer {MOCK_KEY}'
        assert request.get_header('Content-type') == 'application/json'
        payload = json.loads(request.data)
        assert payload['model'] == 'muse-wonder-1.0'
        assert payload['store'] is False
        assert payload['text']['format']['strict'] is True
        assert payload['text']['format']['schema']['properties']['focus']['items']['enum'] == list(EVIDENCE)
        assert MOCK_KEY not in request.data.decode()
        return response()
    monkeypatch.setattr(meta_model, 'open_response', connect)
    assert select_evidence(EVIDENCE) == (['current', 'baseline'], 'llm_evidence_assisted')


def test_disabled_never_resolves_credentials(monkeypatch):
    getter = Mock(side_effect=AssertionError('Credentials must not be accessed'))
    monkeypatch.setattr(meta_model, 'get_api_key', getter)
    monkeypatch.setattr('backend.app.services.ai_assistant.llm_enabled', lambda: False)
    assert select_evidence(EVIDENCE) == (list(EVIDENCE), 'offline_template')
    getter.assert_not_called()


def test_missing_credentials_never_connects(monkeypatch):
    monkeypatch.setattr(meta_model, 'get_api_key', lambda: '')
    assert select_evidence(EVIDENCE) == (list(EVIDENCE), 'offline_template')


@pytest.mark.parametrize('failure', [
    TimeoutError('provider timeout'),
    urllib.error.URLError('network unavailable'),
    urllib.error.HTTPError(meta_model.API_BASE_URL, 401, 'Invalid credential', {}, None),
    urllib.error.HTTPError(meta_model.API_BASE_URL, 429, 'Rate limited', {}, None),
    urllib.error.HTTPError(meta_model.API_BASE_URL, 500, 'Provider unavailable', {}, None),
])
def test_network_failures_fall_back(monkeypatch, failure):
    def fail(request, **kwargs):
        raise failure
    monkeypatch.setattr(meta_model, 'open_response', fail)
    assert select_evidence(EVIDENCE) == (list(EVIDENCE), 'offline_template_fallback')


@pytest.mark.parametrize('focus', [['diagnose_condition'], 'current', [None], [1]])
def test_invalid_evidence_cannot_change_guidance(monkeypatch, focus):
    monkeypatch.setattr(meta_model, 'open_response', lambda request, **kwargs: response(focus))
    assert select_evidence(EVIDENCE) == (list(EVIDENCE), 'offline_template_fallback')


@pytest.mark.parametrize('body', [
    b'not json',
    b'{}',
    json.dumps({'status': 'incomplete', 'output': []}).encode(),
    json.dumps({'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'No'}]}]}).encode(),
    b'x' * (meta_model.MAX_RESPONSE_BYTES + 1),
])
def test_invalid_or_oversized_responses_fall_back(monkeypatch, body):
    monkeypatch.setattr(meta_model, 'open_response', lambda request, **kwargs: io.BytesIO(body))
    assert select_evidence(EVIDENCE) == (list(EVIDENCE), 'offline_template_fallback')


def test_redirects_do_not_forward_credentials():
    request = urllib.request.Request(meta_model.API_BASE_URL, headers={'Authorization': f'Bearer {MOCK_KEY}'})
    handler = meta_model._RejectRedirects()
    assert handler.redirect_request(request, None, 302, 'Found', {}, 'https://example.com') is None


def test_transport_has_a_finite_timeout_and_redirect_guard(monkeypatch, isolated_provider):
    import ssl
    opener = Mock()
    def build(redirects, https):
        assert isinstance(redirects, meta_model._RejectRedirects)
        assert isinstance(https, urllib.request.HTTPSHandler)
        assert https._context.verify_mode == ssl.CERT_REQUIRED
        assert https._context.check_hostname is True
        return opener
    monkeypatch.setattr(meta_model.urllib.request, 'build_opener', build)
    request = urllib.request.Request(meta_model.API_BASE_URL)
    isolated_provider(request)
    opener.open.assert_called_once_with(request, timeout=10)


def test_certifi_supplies_roots_when_python_default_store_is_empty(monkeypatch):
    import ssl
    empty_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    assert empty_context.cert_store_stats()['x509_ca'] == 0
    monkeypatch.setattr(meta_model.ssl, 'create_default_context', lambda: empty_context)
    context = meta_model.tls_context()
    assert context is empty_context
    assert context.cert_store_stats()['x509_ca'] > 0
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_ca_bundle_failure_keeps_offline_fallback(monkeypatch, isolated_provider, tmp_path):
    monkeypatch.setattr(meta_model.certifi, 'where', lambda: str(tmp_path / 'missing-ca.pem'))
    monkeypatch.setattr(meta_model, 'open_response', isolated_provider)
    # Context construction fails before any socket is opened.
    assert select_evidence(EVIDENCE) == (list(EVIDENCE), 'offline_template_fallback')


def test_api_retains_analysis_safety_and_redacts_failures(client, astronaut, monkeypatch, capsys, caplog):
    def fail(request, **kwargs):
        raise RuntimeError(f'Provider failure containing {MOCK_KEY}')
    monkeypatch.setattr(meta_model, 'open_response', fail)
    result = client.post('/api/assessments', headers=astronaut, json={'use_llm': True})
    assert result.status_code == 200
    assert {f['module'] for f in result.json() if f['status'] == 'review_needed'} == {'cardiovascular', 'muscle', 'balance'}
    assert all(f['explanation']['mode'] == 'offline_template_fallback' for f in result.json())
    assert MOCK_KEY not in result.text
    assert 'Provider failure' not in result.text
    symptoms = client.post('/api/symptoms', headers=astronaut, json={
        'description': 'Synthetic warning-sign report', 'severity': 8, 'warning_signs': True,
    })
    assert symptoms.json()['alert']['severity'] == 'urgent'
    assert 'Do not wait for Earth' in symptoms.json()['actions'][0]['text']
    captured = capsys.readouterr()
    assert MOCK_KEY not in captured.out + captured.err + caplog.text


@pytest.mark.parametrize('focus, expected', [([], ['baseline', 'current']), (['current'] * 3, ['current', 'baseline'])])
def test_schema_permitted_empty_and_repeated_ids_are_safe_success(monkeypatch, focus, expected):
    monkeypatch.setattr(meta_model, 'open_response', lambda request, **kwargs: response(focus))
    assert select_evidence(EVIDENCE) == (expected, 'llm_evidence_assisted')


def test_documented_response_with_reasoning_and_multiple_text_parts(monkeypatch):
    body = {
        'id': 'resp_mock', 'object': 'response', 'status': 'completed',
        'model': 'muse-wonder-1.0', 'error': None, 'incomplete_details': None,
        'output': [
            {'type': 'reasoning', 'id': 'rs_mock', 'summary': []},
            {'type': 'message', 'role': 'assistant', 'status': 'completed', 'content': [
                {'type': 'output_text', 'text': '{"focus":', 'annotations': []},
                {'type': 'output_text', 'text': '["current"]}', 'annotations': []},
            ]},
        ],
    }
    monkeypatch.setattr(meta_model, 'open_response', lambda request, **kwargs: io.BytesIO(json.dumps(body).encode()))
    assert select_evidence(EVIDENCE) == (['current', 'baseline'], 'llm_evidence_assisted')


def test_request_matches_responses_contract_and_reasoning_budget(monkeypatch):
    def connect(request, **kwargs):
        payload = json.loads(request.data)
        assert payload['stream'] is False
        assert payload['max_output_tokens'] == 2048
        assert payload['reasoning'] == {'effort': 'minimal'}
        assert 'messages' not in payload and 'response_format' not in payload
        assert [m['role'] for m in payload['input']] == ['system', 'user']
        assert all(m['content'][0]['type'] == 'input_text' for m in payload['input'])
        assert kwargs['timeout'] == 10  # App timeout is unchanged.
        return response()
    monkeypatch.setattr(meta_model, 'open_response', connect)
    assert select_evidence(EVIDENCE)[1] == 'llm_evidence_assisted'


def test_cli_live_explicit_opt_in_bypasses_app_feature_gate(monkeypatch, capsys):
    from scripts import test_meta_connection as connection_check
    monkeypatch.setattr('backend.app.services.ai_assistant.llm_enabled', lambda: False)
    transport = Mock(side_effect=lambda request, **kwargs: response())
    monkeypatch.setattr(meta_model, 'open_response', transport)
    assert connection_check.main(['--live']) == 0  # All credential/HTTP access is mocked.
    transport.assert_called_once()
    assert transport.call_args.kwargs['timeout'] == 60
    assert 'PASS: Live' in capsys.readouterr().out


def test_cli_missing_credentials_diagnostic(monkeypatch, capsys):
    from scripts import test_meta_connection as connection_check
    monkeypatch.setattr(meta_model, 'get_api_key', lambda: '')
    assert connection_check.main(['--live']) == 1
    assert '[missing_credentials]' in capsys.readouterr().out


@pytest.mark.parametrize('failure, code', [
    (TimeoutError(MOCK_KEY), 'timeout'),
    (urllib.error.URLError(MOCK_KEY), 'network_error'),
    (urllib.error.HTTPError(meta_model.API_BASE_URL, 400, MOCK_KEY, {}, io.BytesIO(MOCK_KEY.encode())), 'http_400'),
    (urllib.error.HTTPError(meta_model.API_BASE_URL, 401, MOCK_KEY, {}, None), 'http_401'),
    (urllib.error.HTTPError(meta_model.API_BASE_URL, 429, MOCK_KEY, {}, None), 'http_429'),
    (urllib.error.HTTPError(meta_model.API_BASE_URL, 500, MOCK_KEY, {}, None), 'http_500'),
    (RuntimeError(MOCK_KEY), 'unexpected_error'),
])
def test_cli_failure_codes_do_not_disclose_provider_details(monkeypatch, capsys, caplog, failure, code):
    from scripts import test_meta_connection as connection_check
    def fail(request, **kwargs):
        raise failure
    monkeypatch.setattr(meta_model, 'open_response', fail)
    assert connection_check.main(['--live']) == 1
    captured = capsys.readouterr()
    assert f'[{code}]' in captured.out
    assert MOCK_KEY not in captured.out + captured.err + caplog.text


@pytest.mark.parametrize('wrapped', [False, True])
def test_cli_tls_failure_diagnostic_preserves_certificate_verification(monkeypatch, capsys, wrapped):
    import ssl
    from scripts import test_meta_connection as connection_check
    failure = ssl.SSLCertVerificationError(1, MOCK_KEY)
    def fail(request, **kwargs):
        raise urllib.error.URLError(failure) if wrapped else failure
    monkeypatch.setattr(meta_model, 'open_response', fail)
    assert connection_check.main(['--live']) == 1
    captured = capsys.readouterr()
    assert '[tls_verification_failed]' in captured.out
    assert MOCK_KEY not in captured.out + captured.err


@pytest.mark.parametrize('body, code', [
    ({'status': 'incomplete', 'incomplete_details': {'reason': 'max_output_tokens'}, 'output': []}, 'output_token_limit'),
    ({'status': 'failed', 'error': {'message': MOCK_KEY}, 'output': []}, 'response_not_completed'),
    ({'status': 'completed', 'output': []}, 'empty_output'),
    ({'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal', 'refusal': MOCK_KEY}]}]}, 'refused_response'),
    ({'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': '{"focus":["invented"]}'}]}]}, 'invalid_focus'),
])
def test_cli_http_200_does_not_hide_generation_or_parsing_failures(monkeypatch, capsys, body, code):
    from scripts import test_meta_connection as connection_check
    monkeypatch.setattr(meta_model, 'open_response', lambda request, **kwargs: io.BytesIO(json.dumps(body).encode()))
    assert connection_check.main(['--live']) == 1
    captured = capsys.readouterr()
    assert f'[{code}]' in captured.out
    assert MOCK_KEY not in captured.out + captured.err


def test_cli_default_mock_never_accesses_environment_or_network(monkeypatch, capsys):
    from scripts import test_meta_connection as connection_check
    def forbidden(*args, **kwargs):
        pytest.fail('Default mock attempted environment or network access')
    monkeypatch.setattr(meta_model, 'get_api_key', forbidden)
    monkeypatch.setattr(meta_model, 'open_response', forbidden)
    assert connection_check.main([]) == 0
    assert 'PASS: Mock' in capsys.readouterr().out
