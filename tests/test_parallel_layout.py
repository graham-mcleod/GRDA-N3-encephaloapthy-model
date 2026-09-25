"""Tests for parallel_layout: machine detection, layout choice, MPI commands,
and the calibration file. Linux topologies and container limits are simulated
with temporary sysfs/cgroup trees, so the tests run on any system:

    python -m unittest discover tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import parallel_layout as pl  # noqa: E402

L = pl.Layout


def fake_sysfs(root: Path, topology: dict[int, tuple[int, int]], p_cores: str | None = None) -> Path:
    """Write /sys/devices-style topology files; topology maps cpu -> (package, core)."""
    for cpu, (package, core) in topology.items():
        directory = root / "system" / "cpu" / f"cpu{cpu}" / "topology"
        directory.mkdir(parents=True)
        (directory / "physical_package_id").write_text(f"{package}\n")
        (directory / "core_id").write_text(f"{core}\n")
    if p_cores:
        (root / "cpu_core").mkdir(parents=True)
        (root / "cpu_core" / "cpus").write_text(p_cores + "\n")
    return root


class TemporaryDirectoryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class LinuxCoreDetection(TemporaryDirectoryTest):
    def test_hyperthreading_counts_physical_cores(self):
        root = fake_sysfs(self.tmp, {cpu: (0, cpu % 8) for cpu in range(16)})
        self.assertEqual(pl.linux_physical_cores(set(range(16)), root), (8, "physical cores"))

    def test_affinity_limits_the_count(self):
        root = fake_sysfs(self.tmp, {cpu: (0, cpu % 8) for cpu in range(16)})
        self.assertEqual(pl.linux_physical_cores({0, 8, 1, 9}, root), (2, "physical cores"))

    def test_hybrid_intel_uses_performance_cores(self):
        topology = {cpu: (0, cpu // 2) for cpu in range(12)}  # 6 P-cores with HT
        topology.update({cpu: (0, 100 + cpu) for cpu in range(12, 20)})  # 8 E-cores
        root = fake_sysfs(self.tmp, topology, p_cores="0-11")
        self.assertEqual(pl.linux_physical_cores(set(range(20)), root), (6, "performance cores"))
        self.assertEqual(pl.linux_physical_cores(set(range(12, 20)), root), (8, "physical cores"))

    def test_two_sockets_with_repeated_core_ids(self):
        root = fake_sysfs(self.tmp, {cpu: (cpu // 16, cpu % 16) for cpu in range(32)})
        self.assertEqual(pl.linux_physical_cores(set(range(32)), root), (32, "physical cores"))

    def test_missing_sysfs(self):
        self.assertIsNone(pl.linux_physical_cores({0, 1}, self.tmp / "none"))

    def test_cpu_list(self):
        self.assertEqual(pl.parse_cpu_list("0-3,8,10-11"), {0, 1, 2, 3, 8, 10, 11})


class ContainerLimits(TemporaryDirectoryTest):
    def test_cgroup_v2(self):
        (self.tmp / "cpu.max").write_text("400000 100000\n")
        self.assertEqual(pl.cgroup_cpu_limit(self.tmp), 4)
        (self.tmp / "cpu.max").write_text("max 100000\n")
        self.assertIsNone(pl.cgroup_cpu_limit(self.tmp))

    def test_cgroup_v1(self):
        (self.tmp / "cpu").mkdir()
        (self.tmp / "cpu" / "cpu.cfs_quota_us").write_text("250000\n")
        (self.tmp / "cpu" / "cpu.cfs_period_us").write_text("100000\n")
        self.assertEqual(pl.cgroup_cpu_limit(self.tmp), 2)
        (self.tmp / "cpu" / "cpu.cfs_quota_us").write_text("-1\n")
        self.assertIsNone(pl.cgroup_cpu_limit(self.tmp))


class DefaultLayouts(unittest.TestCase):
    cases = [
        # (description, n_runs, cores, MPI works, expected layout)
        ("laptop, one run", 1, 4, True, L(1, 4, 1)),
        ("12 cores, 9 runs", 9, 12, True, L(1, 12, 1)),
        ("64 cores, one run", 1, 64, True, L(1, 32, 1)),
        ("64 cores, 10 runs", 10, 64, True, L(2, 32, 1)),
        ("128 cores, 3 runs", 3, 128, True, L(3, 32, 1)),
        ("no MPI, one run", 1, 8, False, L(1, 1, 8)),
        ("no MPI, many runs", 20, 12, False, L(12, 1, 1)),
        ("no MPI, fewer runs than cores", 3, 12, False, L(3, 1, 4)),
        ("no MPI, 64 cores, 6 runs", 6, 64, False, L(6, 1, 10)),
        ("single core", 5, 1, True, L(1, 1, 1)),
    ]

    def test_defaults(self):
        for description, n_runs, cores, mpi, expected in self.cases:
            with self.subTest(description):
                self.assertEqual(pl.choose_layout(n_runs, cores, mpi)[0], expected)

    def test_explicit_choices(self):
        self.assertEqual(pl.choose_layout(15, 12, True, ranks=8)[0], L(1, 8, 1))
        self.assertEqual(pl.choose_layout(15, 12, True, ranks=4)[0], L(3, 4, 1))
        self.assertEqual(pl.choose_layout(15, 12, True, jobs=3)[0], L(3, 4, 1))
        self.assertEqual(pl.choose_layout(1, 12, True, threads=2)[0], L(1, 6, 2))
        self.assertEqual(pl.choose_layout(6, 12, False, threads=4)[0], L(3, 1, 4))


class CalibratedLayouts(unittest.TestCase):
    calibration = {
        "mode": "mpi", "created": "2026-09-25T00:00:00",
        "single": {"jobs": 1, "ranks": 12, "threads": 1},
        "sweep": {"jobs": 3, "ranks": 4, "threads": 1},
    }

    def choose(self, n_runs, cores=12, mpi=True, **explicit):
        return pl.choose_layout(n_runs, cores, mpi, self.calibration, **explicit)[0]

    def test_single_and_sweep(self):
        self.assertEqual(self.choose(1), L(1, 12, 1))
        self.assertEqual(self.choose(9), L(3, 4, 1))

    def test_fewer_runs_than_calibrated_jobs(self):
        self.assertEqual(self.choose(2), L(2, 6, 1))

    def test_calibration_larger_than_core_budget_is_ignored(self):
        self.assertEqual(self.choose(9, cores=8), L(1, 8, 1))

    def test_calibration_for_other_mode_is_ignored(self):
        self.assertEqual(self.choose(1, mpi=False), L(1, 1, 12))

    def test_explicit_choice_wins(self):
        self.assertEqual(self.choose(15, ranks=8), L(1, 8, 1))


class MPICommands(unittest.TestCase):
    def test_open_mpi(self):
        mpi = pl.MPI("/usr/bin/mpiexec", "openmpi", "/usr/lib/libmpi.so", [])
        self.assertEqual(mpi.command(4, ["nrniv"], 12, False), ["/usr/bin/mpiexec", "-n", "4", "nrniv"])
        self.assertEqual(mpi.command(4, ["nrniv"], 12, True),
                         ["/usr/bin/mpiexec", "--bind-to", "none", "-n", "4", "nrniv"])
        self.assertEqual(mpi.command(16, ["nrniv"], 12, False),
                         ["/usr/bin/mpiexec", "--oversubscribe", "-n", "16", "nrniv"])

    def test_extra_arguments(self):
        mpi = pl.MPI("/usr/bin/mpiexec", "mpich", None, ["-launcher", "fork"])
        self.assertEqual(mpi.command(4, ["nrniv"], 12, True),
                         ["/usr/bin/mpiexec", "-launcher", "fork", "-n", "4", "nrniv"])

    def test_intel_pinning_off_for_concurrent_jobs(self):
        mpi = pl.MPI("mpiexec", "intel", "/x/libmpi.so", [])
        self.assertEqual(mpi.environment(True), {"MPI_LIB_NRN_PATH": "/x/libmpi.so", "I_MPI_PIN": "0"})
        self.assertEqual(mpi.environment(False), {"MPI_LIB_NRN_PATH": "/x/libmpi.so"})


class SweepCandidates(unittest.TestCase):
    def test_candidates_fill_the_machine(self):
        for cores in (2, 4, 6, 8, 12, 16, 24, 32, 64, 128):
            with self.subTest(cores=cores):
                counts = pl._candidate_job_counts(cores)
                self.assertLessEqual(len(counts), 6)
                self.assertIn(cores, counts)  # one single-rank job per core
                for count in counts:
                    self.assertGreater(count * (cores // count), cores // 2)

    def test_single_core_has_no_sweep_candidates(self):
        self.assertEqual(pl._candidate_job_counts(1), [])


class CalibrationFile(TemporaryDirectoryTest):
    hardware = {"system": "Linux", "arch": "x86_64", "cpu": "X", "usable_cores": 8, "logical_cpus": 16}
    open_mpi = pl.MPI("mpiexec", "openmpi", None, [])
    mpi_entry = {"created": "2026-09-25T10:00:00", "mode": "mpi", "mpi": "openmpi",
                 "single": {"jobs": 1, "ranks": 8, "threads": 1},
                 "sweep": {"jobs": 2, "ranks": 4, "threads": 1}}
    thread_entry = {"created": "2026-09-25T11:00:00", "mode": "threads", "mpi": None,
                    "single": {"jobs": 1, "ranks": 1, "threads": 8},
                    "sweep": {"jobs": 8, "ranks": 1, "threads": 1}}

    def test_no_file(self):
        self.assertEqual(pl.load_calibration(self.tmp, self.hardware, self.open_mpi), (None, ""))

    def test_modes_are_stored_side_by_side(self):
        pl.save_calibration(self.tmp, self.mpi_entry, self.hardware)
        entry, note = pl.load_calibration(self.tmp, self.hardware, None)
        self.assertIsNone(entry)
        self.assertIn("--calibrate --no-mpi", note)
        pl.save_calibration(self.tmp, self.thread_entry, self.hardware)
        self.assertEqual(pl.load_calibration(self.tmp, self.hardware, self.open_mpi)[0]["sweep"],
                         self.mpi_entry["sweep"])
        self.assertEqual(pl.load_calibration(self.tmp, self.hardware, None)[0]["sweep"],
                         self.thread_entry["sweep"])

    def test_other_mpi_implementation_is_ignored(self):
        pl.save_calibration(self.tmp, self.mpi_entry, self.hardware)
        mpich = pl.MPI("mpiexec", "mpich", None, [])
        self.assertIsNone(pl.load_calibration(self.tmp, self.hardware, mpich)[0])

    def test_other_hardware_is_ignored(self):
        pl.save_calibration(self.tmp, self.mpi_entry, self.hardware)
        entry, note = pl.load_calibration(self.tmp, {**self.hardware, "usable_cores": 16}, self.open_mpi)
        self.assertIsNone(entry)
        self.assertIn("different hardware", note)

    def test_older_file_version_is_ignored(self):
        pl.save_calibration(self.tmp, self.mpi_entry, self.hardware)
        path = self.tmp / pl.CALIBRATION_FILE
        data = json.loads(path.read_text())
        data["version"] = pl.CALIBRATION_VERSION - 1
        path.write_text(json.dumps(data))
        entry, note = pl.load_calibration(self.tmp, self.hardware, self.open_mpi)
        self.assertIsNone(entry)
        self.assertIn("older version", note)


if __name__ == "__main__":
    unittest.main()
