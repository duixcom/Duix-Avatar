"""Pure helpers matching the official app_local.py /easy protocol.

No queue, filesystem, renderer, or license behavior is implemented here.
Flags follow the exact official string comparison, including pn default1.
"""
from dataclasses import dataclass


MESSAGES = {9999: '系统异常', 10000: '成功', 10001: '忙碌中',
            10002: '参数异常', 10003: '获取锁异常', 10004: '任务不存在'}


class ParameterError(ValueError):
    pass


def switch(payload, name, default=0):
    if name not in payload or payload[name] == '':
        return default
    return int(str(payload[name]) == '1')


@dataclass(frozen=True)
class SubmitRequest:
    code: str
    audio_url: str
    video_url: str
    watermark_switch: int = 0
    digital_auth: int = 0
    chaofen: int = 0
    pn: int = 1


def parse_submit(payload):
    if not isinstance(payload, dict):
        raise ParameterError('Expected a JSON object')
    # Original ordering and missing-field messages; reject wrong JSON types
    # here instead of allowing an eventual worker/type exception.
    for name in ('audio_url', 'video_url', 'code'):
        if name not in payload or payload[name] == '':
            raise ParameterError(name + '参数缺失')
        if not isinstance(payload[name], str):
            raise ParameterError(name + '必须是字符串')
    return SubmitRequest(payload['code'], payload['audio_url'], payload['video_url'],
                         switch(payload, 'watermark_switch'), switch(payload, 'digital_auth'),
                         switch(payload, 'chaofen'), switch(payload, 'pn', 1))


def response(code, msg=None, data=None, success=None):
    if success is None:
        success = code in (10000, 10001, 10004)
    return {'code': int(code), 'success': bool(success),
            'msg': MESSAGES[code] if msg is None else msg,
            'data': {} if data is None else data}


def submit_success():
    # Official success msg is numeric10000, not its human-readable enum string.
    return response(10000, msg=10000)


def query_success(code, status, progress, result='', msg='', **metrics):
    data = {'code': code, 'status': status, 'progress': progress,
            'result': result, 'msg': msg}
    if status == 2:
        data.update({key: metrics.get(key, 0)
                     for key in ('cost', 'video_duration', 'width', 'height')})
    return response(10000, msg='', data=data)
