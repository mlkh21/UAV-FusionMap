"""Summarize optional Local Map fixture process samples; never a formal M1 gate."""


def mapping_resource_report(rows, errors):
    if errors:
        raise ValueError('resource sampler errors: ' + '; '.join(errors))
    samples = []
    for row in rows:
        for process in row['processes']:
            if process['role'] == 'perf01a_mapping':
                samples.append(dict(monotonic_ns=row['monotonic_ns'],
                                    pid=process['pid'], created=process['created'],
                                    rss_bytes=process['rss_bytes'], cpu_s=process['cpu_s']))
    if len(samples) < 2:
        raise ValueError('mapping process requires two or more resource samples')
    if (len({(row['pid'], row['created']) for row in samples}) != 1
            or any(right['monotonic_ns'] <= left['monotonic_ns']
                   for left, right in zip(samples, samples[1:]))):
        raise ValueError('mapping process identity or sample order changed')
    return dict(schema_version='m1_fixture_resource_v1',
                scope='perf01a_mapping process in local ROS fixture',
                rss_peak_sampled_bytes=max(row['rss_bytes'] for row in samples),
                samples=samples, sample_count=len(samples),
                input_source='software_fixture', hardware_validated=False,
                formal_perf_validated=False, power_validated=False)
