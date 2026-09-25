"""
Vectorized recording of the summed cortical voltage (vcort) and biophysical LFP.

The original implementation summed seg.v and seg.er_xtra over every cortical
segment in a Python callback that NEURON executed on every time step
(cvode.extra_scatter_gather). That per-step Python loop cost about as much as
the entire NEURON integration. This recorder produces bit-identical sums with
no Python work per time step: NEURON records each segment's values in C
(Vector.record), and the sums are formed with NumPy once per data-dump chunk.

Alignment with the legacy callback (verified bit for bit):
  * the callback ran after the voltage update but before the AFTER SOLVE block
    of xtra.mod that computes er_xtra, so on each step it saw the current v but
    the previous step's er_xtra (the INITIAL value on the first step);
  * each buffer therefore holds the sample carried over from the previous chunk
    followed by the new samples, and a chunk uses v samples 1..n and er_xtra
    samples 0..n-1.
Reducing a (segments x samples) array over axis 0 accumulates rows in order,
starting from 0.0, which reproduces the callback's sequential left-to-right sum
exactly. Recording also works unchanged with multiple NEURON threads.
"""

import numpy as np
from neuron import h


class CorticalFieldRecorder:
    """Records v and er_xtra for every segment of the given sections, in order."""

    def __init__(self, sections):
        self._v = []
        self._er = []
        for sec in sections:
            for seg in sec:
                vv = h.Vector()
                vv.record(seg._ref_v)
                self._v.append(vv)
                ev = h.Vector()
                ev.record(seg._ref_er_xtra)
                self._er.append(ev)
        # t is recorded only to know how many steps a chunk contains when this
        # rank owns no cortical segments.
        self._t = h.Vector()
        self._t.record(h._ref_t)

    @staticmethod
    def _ordered_sum(vecs, columns):
        rows = np.stack([vec.as_numpy() for vec in vecs])
        return np.add.reduce(rows[:, columns], axis=0, initial=0.0)

    def collect(self):
        """Return (v_sum, lfp_sum) for the steps integrated since the last call."""
        n = len(self._t) - 1
        if n <= 0:
            return np.zeros(0), np.zeros(0)
        if self._v:
            v_sum = self._ordered_sum(self._v, slice(1, None))
            lfp_sum = self._ordered_sum(self._er, slice(None, -1))
        else:
            v_sum = np.zeros(n)
            lfp_sum = np.zeros(n)
        # keep only the last sample of each buffer; it is sample 0 of the next chunk
        for vec in self._v:
            vec.remove(0, n - 1)
        for vec in self._er:
            vec.remove(0, n - 1)
        self._t.remove(0, n - 1)
        return v_sum, lfp_sum
