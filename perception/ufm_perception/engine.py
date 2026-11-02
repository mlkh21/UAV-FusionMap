"""Synchronous perception business boundary, independent of ROS and research imports."""
import copy

from .input_contract import reject_training_fields, validate_bundle, validate_context
from .modes import disabled_infer, research_infer
from .output_contract import validate_geometry, validate_output
from .placeholder import placeholder_infer
from .unavailable import unavailable_infer


class UntrustedInputError(ValueError):
    """No business observation may be fabricated from this input context."""


class PerceptionEngine:
    def __init__(self, run_id, mode='placeholder', resolution=(.5, .5, .5),
                 shape=(64, 32, 16), origin=(-16., -8., -4.), rolling_grid=False,
                 max_delta_ns=5_000_000, max_pose_age_ns=10_000_000, preflight=None):
        if mode not in ('disabled', 'placeholder', 'research'):
            raise ValueError('unsupported perception mode: ' + str(mode))
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError('run_id required')
        if any(type(value) is not int or value < 0 for value in (max_delta_ns, max_pose_age_ns)):
            raise ValueError('bundle age limits must be nonnegative integers')
        validate_geometry(resolution, shape, origin)
        self.run_id, self.mode = run_id, mode
        self.geometry = dict(resolution=tuple(resolution), shape=tuple(shape), origin=tuple(origin))
        self.rolling_grid = rolling_grid
        self.max_delta_ns, self.max_pose_age_ns = max_delta_ns, max_pose_age_ns
        self.preflight = copy.deepcopy(preflight)

    def _trusted(self, bundle):
        try:
            if bundle['header']['run_id'] != self.run_id:
                raise ValueError('bundle run differs from configured node run')
            validate_context(bundle)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise UntrustedInputError(str(exc)) from exc

    def failure(self, bundle, reason):
        self._trusted(bundle)
        return unavailable_infer(bundle, reason,
            source_type='model' if self.mode == 'research' else 'derived', **self.geometry)

    def process(self, bundle):
        self._trusted(bundle)
        # Keep the trusted identity/context isolated from a mutating backend.
        submitted = copy.deepcopy(bundle)
        try:
            reject_training_fields(submitted)
            validate_bundle(submitted, self.max_delta_ns, self.max_pose_age_ns)
            result = self._infer(submitted)
            validate_output(result, bundle, self.mode, rolling_grid=self.rolling_grid, **self.geometry)
            return result
        except Exception as exc:
            return self.failure(bundle, type(exc).__name__ + ':' + str(exc))

    def _infer(self, bundle):
        if self.mode == 'placeholder':
            return placeholder_infer(bundle, rolling_grid=self.rolling_grid, **self.geometry)
        if self.mode == 'disabled':
            return disabled_infer(bundle, **self.geometry)
        return research_infer(bundle, preflight=self.preflight, **self.geometry)
