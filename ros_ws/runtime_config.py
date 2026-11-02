"""ROS装配层读取共享fixture配置，业务模块只接收显式参数。"""
from pathlib import Path
import yaml


DEFAULT_MAP_CONFIG = Path(__file__).resolve().parents[1] / 'configs/local_map_fixture.yaml'


def normalize_map_config(values):
    """兼容旧小整数和ROS纳秒字符串快照，业务计算始终使用精确整数。"""
    values = dict(values)
    duration = values['staleness_limit_ns']
    if isinstance(duration, str) and duration.isascii() and duration.isdecimal():
        duration = int(duration)
    if type(duration) is not int or not 0 <= duration < 2**63:
        raise ValueError('staleness_limit_ns must be nonnegative int64 nanoseconds')
    values['staleness_limit_ns'] = duration
    return values


def ros_map_config(values):
    values = normalize_map_config(values)
    values['staleness_limit_ns'] = str(values['staleness_limit_ns'])
    return values


def load_map_config(path=None):
    with Path(path or DEFAULT_MAP_CONFIG).open(encoding='utf-8') as handle:
        value = yaml.safe_load(handle)
    fields = {'schema_version', 'map_id', 'resolution', 'shape', 'origin',
              'staleness_limit_ns', 'max_active_cells'}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('local map configuration fields differ from local_map_fixture.v1')
    if value['schema_version'] != 'local_map_fixture.v1':
        raise ValueError('unsupported local map configuration schema')
    return normalize_map_config({key: item for key, item in value.items() if key != 'schema_version'})


def map_settings(get_param):
    values = load_map_config(get_param('/ufm_local_map_config', ''))
    return normalize_map_config({key: get_param('~' + key, default)
                                 for key, default in values.items()})


def load_m2_config(path):
    if not path:
        raise ValueError('m2_fixture requires explicit m2_fixture_config path')
    from ufm_mapping.m2_contract import validate_spec
    with Path(path).open(encoding='utf-8') as handle:
        values = yaml.safe_load(handle)
    if not isinstance(values, dict):
        raise ValueError('M2 fixture configuration must be a mapping')
    validate_spec(values)
    return values


def load_m3_config(path):
    if not path:
        raise ValueError('m3_fixture requires explicit m3_fixture_config path')
    from ufm_mapping.m3_contract import validate_spec
    with Path(path).open(encoding='utf-8') as handle:
        values = yaml.safe_load(handle)
    if not isinstance(values, dict):
        raise ValueError('M3 fixture configuration must be a mapping')
    validate_spec(values)
    return values


def load_m4_config(path):
    if not path:
        raise ValueError('m4_fixture requires explicit m4_fixture_config path')
    from ufm_mapping.m4_contract import validate_spec
    with Path(path).open(encoding='utf-8') as handle:
        values = yaml.safe_load(handle)
    validate_spec(values)
    return values
