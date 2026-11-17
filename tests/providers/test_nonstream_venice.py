"""Spec 2026-11-17-broken-letters-guard: Venice answers memory and unit-reviewed stages without streaming."""
import json
import threading
import time

import httpx
import pytest

from storygen.generation.context import ContextBundle
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.requests import generation_request
from storygen.providers.streaming import build_generation_gateway
from tests.providers.test_venice import model


def settings(provider='venice', edit_mode='prose'):
    return RoleSettings(provider=ProviderSettings(provider=provider, model='qwen-test', include_usage=True,
                        response_mode='prompt_json'), memory_mode='evidence_delta', edit_mode=edit_mode)


@pytest.mark.parametrize('stage,edit_mode,provider,streamed', [
    ('memory', 'prose', 'venice', False),
    ('classify', 'prose', 'venice', False),
    ('edit', 'diff', 'venice', False),
    ('edit', 'patches', 'venice', False),
    ('rewrite', 'prose', 'venice', False),
    ('edit', 'prose', 'venice', True),
    ('draft', 'prose', 'venice', True),
    ('memory', 'prose', 'local', True),
])
def test_only_venice_reject_and_unit_stages_wait_for_the_whole_answer(stage, edit_mode, provider, streamed):
    body = generation_request(stage, settings(provider, edit_mode), 'система', 'текст', {})
    assert body['stream'] is streamed
    assert ('stream_options' in body) is streamed


def context():
    return ContextBundle(story_id='s', scene_id='c', stage='memory', scene_revision=0, story_revision=0, settings=settings(),
                         system_text='Наш промпт', user_text='Точний авторський текст.', input_refs=[], fingerprint='f',
                         estimated_tokens=10)


def completion(text='{"ok": true}'):
    return {'id': 'r', 'object': 'chat.completion', 'created': 0, 'model': 'qwen-test',
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': text}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 3, 'total_tokens': 13}, 'cost': {'usd': .001, 'diem': 0}}


def test_whole_answer_becomes_one_delta_and_a_terminal_with_cost(monkeypatch, accounted_call):
    monkeypatch.setenv('VENICE_API_KEY', 'test')
    sent = []
    def handler(request):
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [model()]})
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=completion())
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        events = list(build_generation_gateway(context().settings.provider, client, accounted_call('venice', 'qwen-test'))
                      .stream(context(), threading.Event()))
    assert [e.type for e in events] == ['delta', 'terminal']
    assert events[0].text == '{"ok": true}'
    assert events[-1].usage['cost'] == {'usd': .001, 'diem': 0} and events[-1].usage['total_tokens'] == 13
    assert sent[0]['stream'] is False


def test_the_whole_answer_gets_a_300_second_read_timeout_and_errors_stay_generation_errors(monkeypatch, accounted_call):
    monkeypatch.setenv('VENICE_API_KEY', 'test')
    timeouts = []
    def handler(request):
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [model()]})
        timeouts.append(request.extensions['timeout']['read'])
        return httpx.Response(503, json={'error': {'message': 'busy'}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        events = list(build_generation_gateway(context().settings.provider, client, accounted_call('venice', 'qwen-test'))
                      .stream(context(), threading.Event()))
    assert timeouts == [300]
    assert events[-1].type == 'error' and events[-1].failure['http_status'] == 503


def test_cancel_returns_at_once_and_the_late_answer_closes_the_budget_record(monkeypatch, accounted_call):
    monkeypatch.setenv('VENICE_API_KEY', 'test')
    release = threading.Event()
    def handler(request):
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [model()]})
        release.wait(5)
        return httpx.Response(200, json=completion())
    accounting = accounted_call('venice', 'qwen-test')
    finished = []
    original = accounting.finish
    def spy(*args, **kwargs):
        finished.append(kwargs)
        return original(*args, **kwargs)
    accounting.finish = spy
    cancel = threading.Event()
    threading.Timer(0.3, cancel.set).start()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        started = time.monotonic()
        events = list(build_generation_gateway(context().settings.provider, client, accounting).stream(context(), cancel))
        elapsed = time.monotonic()-started
        assert events[-1].type == 'cancelled' and elapsed < 2
        assert finished == []
        release.set()
        deadline = time.monotonic()+3
        while not finished and time.monotonic() < deadline:
            time.sleep(0.05)
    assert len(finished) == 1
    assert finished[0]['cost'] == {'usd': .001, 'diem': 0} and finished[0]['complete'] is True
    deadline = time.monotonic()+3
    while (row := accounting.repo.billing('calls', scope='cli:mock')[0])['state'] != 'settled' and time.monotonic() < deadline:
        time.sleep(0.05)
    assert row['state'] == 'settled' and row['cost_source'] == 'provider', row
