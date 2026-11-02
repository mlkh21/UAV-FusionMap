"""Compare saved independent checkpoints to actual public/test diagnostic receipts."""
from fractions import Fraction
import math
import struct


def float32(value):
    return struct.unpack('<f',struct.pack('<f',float(value)))[0]


def connected_outputs(bus_info,required):
    counts = {topic:0 for topic in required}
    for row in bus_info:
        if len(row)>=6 and row[2]=='o' and row[5] is True and row[4] in counts:
            counts[row[4]] += 1
    return all(counts[topic]>=count for topic,count in required.items())


def compare(actual,expected,bindings):
    differences = []
    for key,wanted in expected.items():
        if key not in actual:
            differences.append(key+': missing actual receipt')
            continue
        value = actual[key]
        if key == 'terrain.instance':
            valid = type(value) is str and bool(value.strip())
            if wanted == '$first':
                valid = valid and (key not in bindings or value == bindings[key])
                if valid: bindings[key] = value
            elif wanted == '$different':
                valid = valid and key in bindings and value != bindings[key]
            else:
                valid = False
        elif key == 'recording.event_ceiling':
            valid = type(value) is int and 0 <= value <= wanted
        elif key == 'map.probability' and wanted is not None:
            valid = type(value) is float and value == float32(wanted)
        elif key == 'terrain.height' and wanted is not None:
            valid = type(value) in (int,float) and value == wanted
        elif key == 'map.interval' and wanted is not None:
            valid = type(value) is list and len(value) == 2 and all(
                type(v) is float and math.isclose(v,float(Fraction(w)),rel_tol=0.,abs_tol=1e-12)
                for v,w in zip(value,wanted))
        elif key in ('geometry.point','geometry.error_m'):
            values,targets = (value,wanted) if isinstance(wanted,list) else ([value],[wanted])
            valid = isinstance(values,list) and len(values) == len(targets) and all(
                type(v) in (int,float) and not isinstance(v,bool) and
                math.isclose(v,w,rel_tol=0.,abs_tol=1e-9) for v,w in zip(values,targets))
        else:
            valid = type(value) is type(wanted) and value == wanted
        if not valid:
            differences.append('%s: actual=%r expected=%r' % (key,value,wanted))
    return differences


def verify_receipts(expected,receipts):
    by_event = {row['event_id']:row for row in receipts}
    if len(by_event) != len(receipts):
        raise ValueError('duplicate actual event receipt')
    rows,bindings = [],{}
    for check in expected['checks']:
        actual = by_event.get(check['after'])
        errors = ['event missing'] if actual is None else compare(actual['values'],check['values'],bindings)
        rows.append(dict(event_id=check['after'],passed=not errors,errors=errors,
                         expected=check['values'],actual=None if actual is None else actual['values']))
    return dict(passed=all(r['passed'] for r in rows),checks=rows,
                checked_values=sum(len(r['expected']) for r in rows),bindings=bindings)
