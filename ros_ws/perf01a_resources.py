"""仅采样本次runner进程树；不改变主机频率、亲和性或温度控制。"""
import os
from pathlib import Path
import threading
import time

import psutil

from perf01a_metrics import percentile_set


class ResourceSampler:
    def __init__(self, interval_s=.5):
        self.interval_s = interval_s
        self.rows = []
        self.errors = []
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name='perf01a-resources', daemon=True)
        self.root = psutil.Process()
        cpus = self.root.cpu_affinity()
        self.frequency_cpus = cpus[::max(1, len(cpus) // 4)][:4]
        self.initial_temperatures = {key: [x.current for x in values]
                                     for key, values in psutil.sensors_temperatures().items()}

    def start(self):
        self.thread.start()

    def _run(self):
        while not self.stop_event.is_set():
            started = time.monotonic_ns()
            cpu_started = time.thread_time_ns()
            try:
                processes = []
                for process in [self.root] + self.root.children(recursive=True):
                    try:
                        with process.oneshot():
                            args = process.cmdline()
                            role = next((a.split(':=', 1)[1] for a in args if a.startswith('__name:=')),
                                        'observer' if process.pid == os.getpid() else process.name())
                            cpu = process.cpu_times()
                            switches = process.num_ctx_switches()
                            processes.append(dict(pid=process.pid, created=process.create_time(), role=role,
                                argv=args, cpu_s=cpu.user + cpu.system, rss_bytes=process.memory_info().rss,
                                voluntary_switches=switches.voluntary, involuntary_switches=switches.involuntary))
                    except psutil.NoSuchProcess:
                        continue
                frequencies = {}
                for cpu in self.frequency_cpus:
                    try:
                        frequencies[str(cpu)] = float(Path('/sys/devices/system/cpu/cpu%d/cpufreq/scaling_cur_freq'
                                                           % cpu).read_text()) / 1000.
                    except (OSError, ValueError):
                        frequencies[str(cpu)] = None
                self.rows.append(dict(monotonic_ns=started, processes=processes, load_average=list(os.getloadavg()),
                    representative_frequency_mhz=frequencies,
                    sampling_wall_ns=time.monotonic_ns() - started,
                    sampling_thread_cpu_ns=time.thread_time_ns() - cpu_started))
            except (OSError, psutil.Error) as exc:
                self.errors.append(type(exc).__name__ + ': ' + str(exc))
            self.stop_event.wait(self.interval_s)

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=5.)
        if self.thread.is_alive():
            raise RuntimeError('resource sampler did not stop')

    def report(self, active_window=None):
        rows = [r for r in self.rows if active_window is None or
                active_window[0] <= r['monotonic_ns'] <= active_window[1]]
        series = {}
        for row in rows:
            for process in row['processes']:
                series.setdefault((process['pid'], process['created']), []).append((row['monotonic_ns'], process))
        summary = []
        for (pid, created), samples in series.items():
            rates = [100. * (right[1]['cpu_s'] - left[1]['cpu_s']) /
                     ((right[0] - left[0]) / 1e9) for left, right in zip(samples, samples[1:])]
            summary.append(dict(pid=pid, created=created, role=samples[0][1]['role'], samples=len(samples),
                cpu_seconds_delta=samples[-1][1]['cpu_s'] - samples[0][1]['cpu_s'],
                peak_sampled_rss_bytes=max(p['rss_bytes'] for _, p in samples),
                cpu_percent_one_core=percentile_set(rates)))
        required = {'observer', 'perf01a_source', 'perf01a_sensor', 'perf01a_perception', 'perf01a_mapping'}
        covered = {s['role'] for s in summary if s['samples'] >= 2}
        return dict(sampler_version='2.1', interval_s=self.interval_s, active_window_ns=active_window,
                    initial_temperatures_c=self.initial_temperatures, frequency_cpus=self.frequency_cpus,
                    frequency_scope='four representative allowed CPUs, not per-node frequency',
                    cpu_percent_semantics='100 percent = one logical CPU; between first/last active samples',
                    errors=self.errors, missing_roles=sorted(required - covered), processes=summary,
                    sampling_wall_ns=percentile_set([r['sampling_wall_ns'] for r in rows]),
                    sampling_thread_cpu_ns=percentile_set([r['sampling_thread_cpu_ns'] for r in rows]))
