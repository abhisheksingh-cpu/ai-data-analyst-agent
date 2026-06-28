import redis
import json
import hashlib
import os
redis_host = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=redis_host, port=6379, decode_responses=True, socket_timeout=30)

def make_cache_key(*args):
    raw = "|".join(args)
    return hashlib.sha256(raw.encode()).hexdigest()

def get_cached(key):
    value = r.get(key)
    if value:
        return json.loads(value)
    return None

def set_cached(key, value, ttl_seconds=3600):
    r.set(key, json.dumps(value), ex=ttl_seconds)

def push_task(queue_name, task_dict):
    r.lpush(queue_name, json.dumps(task_dict))

def pop_task(queue_name, timeout=10):
    try:
        result = r.brpop(queue_name, timeout=timeout)
    except redis.exceptions.TimeoutError:
        return None
    if result:
        _, task_json = result
        return json.loads(task_json)
    return None

def pop_result(result_queue, timeout=10):
    try:
        result = r.brpop(result_queue, timeout=timeout)
    except redis.exceptions.TimeoutError:
        return None
    if result:
        _, result_json = result
        return json.loads(result_json)
    return None

def push_result(result_queue, result_dict):
    r.lpush(result_queue, json.dumps(result_dict))

