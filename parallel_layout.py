"""
Machine-adaptive parallel layout for running this model.

Detects the usable CPU cores and the MPI installation of the current machine,
chooses how many simulations to run at once and how many MPI ranks (or NEURON
threads) each gets, and can calibrate that choice by timing short simulations
on the machine (``python run_sweep.py --calibrate``). The calibration is saved
in ``.parallel_layout.json`` in the working directory and is used only on the
machine that produced it. Used by run_sweep.py.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

CALIBRATION_FILE = ".parallel_layout.json"
CALIBRATION_VERSION = 2

# The network has 800 cells. Below ~25 cells per rank the per-step work is too
# small to hide the spike exchange, so without a calibration wider jobs are
# not assumed to help; the rest of a large machine goes to concurrent runs.
MAX_USEFUL_WIDTH = 32

# Layouts within this fraction of the best measured one count as equally good
# (about the run-to-run timing noise of 1-s calibration runs); the calibration
# then prefers fewer concurrent jobs and fewer ranks.
TIE_TOLERANCE = 0.05

RUN_TIME = re.compile(r"Run time for \d+ sec sim = ([\d.]+) sec")


# ---------------------------------------------------------------- cores ----

@dataclass
class Cores:
    usable: int   # cores used by default: physical (performance) cores available to this process
    logical: int  # logical CPUs available to this process
    source: str   # how ``usable`` was determined


def _output(command: list[str], timeout: float = 20) -> str:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _sysctl_int(name: str) -> int | None:
    value = _output(["sysctl", "-n", name]).strip()
    return int(value) if value.isdigit() and int(value) > 0 else None


def parse_cpu_list(text: str) -> set[int]:
    """Parse a Linux CPU list such as ``0-7,16-23``."""
    cpus: set[int] = set()
    for part in text.strip().split(","):
        if "-" in part:
            first, last = part.split("-")
            cpus.update(range(int(first), int(last) + 1))
        elif part:
            cpus.add(int(part))
    return cpus


def linux_physical_cores(cpus: set[int], devices: Path = Path("/sys/devices")) -> tuple[int, str] | None:
    """Count physical cores among ``cpus``; on hybrid Intel CPUs, only performance cores."""
    source = "physical cores"
    performance = devices / "cpu_core" / "cpus"
    if performance.exists():
        try:
            p_cpus = parse_cpu_list(performance.read_text())
        except (OSError, ValueError):
            p_cpus = set()
        if cpus & p_cpus:
            cpus, source = cpus & p_cpus, "performance cores"
    cores = set()
    for cpu in cpus:
        topology = devices / "system" / "cpu" / f"cpu{cpu}" / "topology"
        try:
            key = tuple(
                (topology / name).read_text().strip()
                for name in ("physical_package_id", "die_id", "core_id")
                if (topology / name).exists()
            )
        except OSError:
            return None
        if not key:
            return None
        cores.add(key)
    return (len(cores), source) if cores else None


def cgroup_cpu_limit(root: Path = Path("/sys/fs/cgroup")) -> int | None:
    """CPU quota of the enclosing container (cgroup v2 or v1), or None if unlimited."""
    try:
        quota, period = (root / "cpu.max").read_text().split()[:2]
        return None if quota == "max" else max(1, int(quota) // int(period))
    except (OSError, ValueError):
        pass
    try:
        quota = int((root / "cpu" / "cpu.cfs_quota_us").read_text())
        period = int((root / "cpu" / "cpu.cfs_period_us").read_text())
        return max(1, quota // period) if quota > 0 else None
    except (OSError, ValueError):
        return None


def detect_cores() -> Cores:
    """Physical (performance) cores this process may use.

    Hyperthreads and efficiency cores are excluded because every MPI rank
    waits for the slowest one at each spike exchange; ``--calibrate`` tests
    whether they help anyway. CPU affinity (e.g. a cluster allocation) and
    container quotas are respected. FINK_CORES overrides the result.
    """
    affinity = None
    if hasattr(os, "sched_getaffinity"):
        try:
            affinity = set(os.sched_getaffinity(0))
        except OSError:
            affinity = None
    if hasattr(os, "process_cpu_count"):
        logical = os.process_cpu_count() or 1
    else:
        logical = len(affinity) if affinity else (os.cpu_count() or 1)

    usable, source = None, "logical CPUs"
    system = platform.system()
    if system == "Darwin":
        for name, label in (("hw.perflevel0.physicalcpu", "performance cores"),
                            ("hw.physicalcpu", "physical cores")):
            usable = _sysctl_int(name)
            if usable:
                source = label
                break
    elif system == "Linux":
        found = linux_physical_cores(affinity or set(range(logical)))
        if found:
            usable, source = found
    else:
        try:
            import psutil  # optional; gives physical cores on Windows
            usable = psutil.cpu_count(logical=False)
            source = "physical cores"
        except ImportError:
            pass
    usable = min(usable or logical, logical)

    limit = cgroup_cpu_limit() if system == "Linux" else None
    if limit:
        logical = min(logical, limit)
        if limit < usable:
            usable, source = limit, "container CPU quota"
    if os.environ.get("FINK_CORES"):
        usable, source = int(os.environ["FINK_CORES"]), "FINK_CORES"
    return Cores(max(1, usable), max(1, logical), source)


def cpu_model() -> str:
    if platform.system() == "Darwin":
        model = _output(["sysctl", "-n", "machdep.cpu.brand_string"]).strip()
        if model:
            return model
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.lower().startswith(("model name", "hardware", "cpu model")):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


# ------------------------------------------------------------------ MPI ----

@dataclass
class MPI:
    launcher: str        # mpiexec, mpirun, or srun
    implementation: str  # openmpi, mpich, intel, slurm, or unknown
    library: str | None  # MPI_LIB_NRN_PATH for NEURON's dynamic MPI loading
    extra_args: list[str]

    def command(self, ranks: int, program: list[str], cores: int, concurrent: bool) -> list[str]:
        """Launch ``program`` on ``ranks`` ranks.

        Open MPI binds ranks to cores on Linux; each concurrent mpiexec would
        bind to the same first cores, so binding is disabled for concurrent jobs.
        """
        command = [self.launcher, *self.extra_args]
        if self.implementation == "openmpi":
            if hasattr(os, "geteuid") and os.geteuid() == 0:
                command.append("--allow-run-as-root")
            if ranks > cores:
                command.append("--oversubscribe")
            if concurrent:
                command += ["--bind-to", "none"]
        return command + ["-n", str(ranks), *program]

    def environment(self, concurrent: bool) -> dict[str, str]:
        env = {"MPI_LIB_NRN_PATH": self.library} if self.library else {}
        if concurrent and self.implementation == "intel":
            env["I_MPI_PIN"] = "0"  # same reason as --bind-to none above
        return env


def find_mpi_library(launcher: str | None) -> str | None:
    """Locate the libmpi that belongs to ``launcher`` (NEURON loads MPI at run time)."""
    if os.environ.get("MPI_LIB_NRN_PATH"):
        return os.environ["MPI_LIB_NRN_PATH"]
    if sys.platform == "win32":
        return None
    names = (["libmpi.dylib", "libmpich.dylib"] if sys.platform == "darwin"
             else ["libmpi.so", "libmpi.so.40", "libmpi.so.12", "libmpich.so", "libmpich.so.12"])
    directories: list[Path] = []
    if launcher:
        # prefer the unversioned prefix (e.g. /opt/homebrew) over the resolved one
        for binary in (Path(launcher), Path(os.path.realpath(launcher))):
            directories += [binary.parent.parent / "lib", binary.parent.parent / "lib64"]
    for option in ("-showme:libdirs", "-show"):  # Open MPI, then MPICH wrappers
        text = _output(["mpicc", option]) if shutil.which("mpicc") else ""
        directories += [Path(d[2:] if d.startswith("-L") else d) for d in text.split()
                        if d.startswith(("-L", "/"))]
    if os.environ.get("CONDA_PREFIX"):
        directories.append(Path(os.environ["CONDA_PREFIX"]) / "lib")
    directories += [Path(p) for p in (
        "/opt/homebrew/lib", "/usr/local/lib", "/opt/local/lib/openmpi-mp", "/opt/local/lib/mpich-mp",
        "/usr/lib/x86_64-linux-gnu/openmpi/lib", "/usr/lib/aarch64-linux-gnu/openmpi/lib",
        "/usr/lib64/openmpi/lib", "/usr/lib64/mpich/lib",
        "/usr/lib/x86_64-linux-gnu", "/usr/lib/aarch64-linux-gnu", "/usr/lib64",
    )]
    for directory in directories:
        for name in names:
            if (directory / name).exists():
                return str(directory / name)
    return None


def detect_mpi(launcher: str | None = None) -> MPI | None:
    """Find an MPI launcher (``launcher``, FINK_MPIEXEC, mpiexec, mpirun, or srun in Slurm)."""
    launcher = launcher or os.environ.get("FINK_MPIEXEC")
    if launcher:
        path = shutil.which(launcher) or (launcher if Path(launcher).exists() else None)
    else:
        path = shutil.which("mpiexec") or shutil.which("mpirun")
        if not path and os.environ.get("SLURM_JOB_ID"):
            path = shutil.which("srun")
    if not path:
        return None
    version = _output([path, "--version"]).lower()
    if Path(path).name == "srun":
        implementation = "slurm"
    elif any(tag in version for tag in ("open mpi", "open-mpi", "openrte", "prrte")):
        implementation = "openmpi"
    elif "hydra" in version or "mpich" in version:
        implementation = "mpich"
    elif "intel" in version:
        implementation = "intel"
    else:
        implementation = "unknown"
    return MPI(path, implementation, find_mpi_library(path),
               shlex.split(os.environ.get("FINK_MPIEXEC_ARGS", "")))


def mpi_works(mpi: MPI, nrniv: str, cores: int) -> tuple[bool, str]:
    """Run a 2-rank NEURON job and confirm both ranks see nhost=2."""
    with tempfile.TemporaryDirectory(prefix="syn-brain-mpi-") as tmp:
        script = Path(tmp) / "mpi_check.py"
        script.write_text(
            "from neuron import h\npc = h.ParallelContext()\n"
            "print('NHOST %d' % int(pc.nhost()))\npc.barrier()\nh.quit()\n"
        )
        command = mpi.command(2, [nrniv, "-mpi", "-python", str(script)], max(cores, 2), False)
        env = dict(os.environ, **mpi.environment(False))
        try:
            result = subprocess.run(command, cwd=tmp, env=env, capture_output=True,
                                    text=True, timeout=180)
        except (OSError, subprocess.SubprocessError) as error:
            return False, str(error)
    if result.stdout.count("NHOST 2") == 2:
        return True, ""
    lines = []  # every rank prints the same error; keep each line once
    for line in (result.stdout + result.stderr).splitlines():
        line = line.strip()
        if line and not set(line) <= set("-=") and line not in lines:
            lines.append(line)
    tried = f"MPI_LIB_NRN_PATH={mpi.library}\n" if mpi.library else ""
    return False, tried + "\n".join(
        line if len(line) <= 160 else line[:157] + "..." for line in lines[:4]
    )


# ----------------------------------------------------------- mechanisms ----

def mechanism_library(workdir: Path) -> Path | None:
    """Compiled mechanisms (nrnivmodl output), preferring this machine's architecture."""
    directories = [workdir / platform.machine()]
    directories += sorted(p for p in workdir.iterdir() if p.is_dir() and p not in directories)
    for directory in directories:
        for name in ("libnrnmech.dylib", "libnrnmech.so", ".libs/libnrnmech.so", "special"):
            if (directory / name).exists():
                return directory / name
    dll = workdir / "nrnmech.dll"
    return dll if dll.exists() else None


def mechanisms_need_build(workdir: Path) -> str | None:
    """Why the mechanisms must be (re)compiled, or None if they are current."""
    library = mechanism_library(workdir)
    if library is None:
        return "no compiled mechanisms found"
    mod_files = list((workdir / "mod").glob("*.mod"))
    if mod_files and max(p.stat().st_mtime for p in mod_files) > library.stat().st_mtime:
        return "mod/ has changed since the mechanisms were compiled"
    return None


def build_mechanisms(workdir: Path, bindir: Path) -> None:
    nrnivmodl = shutil.which("nrnivmodl", path=str(bindir)) or shutil.which("nrnivmodl")
    if nrnivmodl is None:
        raise RuntimeError("nrnivmodl not found; compile the mechanisms with NEURON's tools")
    log = workdir / "nrnivmodl.log"
    with log.open("w") as stream:
        code = subprocess.call([nrnivmodl, "mod"], cwd=workdir, stdout=stream, stderr=subprocess.STDOUT)
    if code != 0 or mechanism_library(workdir) is None:
        raise RuntimeError(f"nrnivmodl failed; see {log}")


# --------------------------------------------------------------- layout ----

@dataclass(frozen=True)
class Layout:
    jobs: int     # simulations running at the same time
    ranks: int    # MPI ranks per simulation (1 = no MPI)
    threads: int  # NEURON threads per rank

    @property
    def width(self) -> int:
        return self.ranks * self.threads

    def describe(self) -> str:
        return f"{self.jobs} concurrent job(s) x {self.ranks} rank(s) x {self.threads} thread(s)"


def _parallel_unit(width: int, use_mpi: bool, per_rank_threads: int) -> Layout:
    return Layout(1, width, per_rank_threads) if use_mpi else Layout(1, 1, width)


def choose_layout(
    n_runs: int,
    cores: int,
    use_mpi: bool,
    calibration: dict | None = None,
    jobs: int | None = None,
    ranks: int | None = None,
    threads: int | None = None,
) -> tuple[Layout, str]:
    """Pick (jobs, ranks, threads) for ``n_runs`` simulations on ``cores`` cores.

    Explicit choices win; otherwise a calibration for this machine is used;
    otherwise a default: a single run gets min(cores, MAX_USEFUL_WIDTH)
    workers. For several runs with MPI, each run also gets that many ranks and
    the remaining cores run further simulations concurrently; without MPI,
    single-thread simulations run side by side, because NEURON threads
    synchronize on every time step while separate processes never do. Workers
    are MPI ranks when MPI works and NEURON threads otherwise.
    """
    if not use_mpi:
        ranks = 1
    elif threads is None:
        threads = 1
    # width of one simulation in the unit that is being chosen (ranks or threads)
    fixed = ranks if use_mpi else threads
    per_worker = (threads or 1) if use_mpi else 1

    def build(n_jobs: int, width: int) -> Layout:
        unit = _parallel_unit(width, use_mpi, per_worker)
        return Layout(max(1, min(n_jobs, n_runs)), unit.ranks, unit.threads)

    if jobs and fixed:
        return build(jobs, fixed), "as requested"
    if fixed:
        return build(max(1, cores // (fixed * per_worker)), fixed), "as requested"
    if jobs:
        return build(jobs, max(1, cores // (jobs * per_worker))), "as requested"

    mode = "mpi" if use_mpi else "threads"
    if calibration and calibration.get("mode") == mode and per_worker == 1:
        single, sweep = Layout(**calibration["single"]), Layout(**calibration["sweep"])
        if max(single.width, sweep.jobs * sweep.width) <= cores:
            if n_runs == 1:
                return single, f"calibrated on {calibration['created'][:10]}"
            if n_runs >= sweep.jobs:
                return sweep, f"calibrated on {calibration['created'][:10]}"
            return (build(n_runs, min(single.width, cores // n_runs)),
                    f"calibrated on {calibration['created'][:10]}")

    note = "default (run with --calibrate to tune this machine)"
    widest = max(1, min(cores // per_worker, MAX_USEFUL_WIDTH))
    if n_runs == 1:
        return build(1, widest), note
    width = widest if use_mpi else 1
    n_jobs = max(1, cores // (width * per_worker))
    if n_runs < n_jobs:  # fewer runs than slots: give each run a larger share
        n_jobs, width = n_runs, max(1, min(MAX_USEFUL_WIDTH, cores // (n_runs * per_worker)))
    return build(n_jobs, width), note


# ---------------------------------------------------------- simulations ----

def simulation_command(layout: Layout, mpi: MPI | None, nrniv: str, cores: int,
                       script: str = "bazh_net.py") -> list[str]:
    if layout.ranks == 1:
        return [nrniv, "-python", script]
    assert mpi is not None
    return mpi.command(layout.ranks, [nrniv, "-mpi", "-python", script], cores, layout.jobs > 1)


def simulation_environment(layout: Layout, mpi: MPI | None, state: int, seed: int,
                           duration_ms: float) -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("MPLBACKEND", "Agg")
    env.update(FINK_STATE=str(state), FINK_SEED=str(seed),
               FINK_DURATION_MS=repr(float(duration_ms)), FINK_NTHREAD=str(layout.threads))
    if layout.ranks > 1 and mpi is not None:
        env.update(mpi.environment(layout.jobs > 1))
    return env


def prepare_run_directory(directory: Path, workdir: Path) -> None:
    """A scratch copy of the model code that shares the compiled mechanisms."""
    directory.mkdir(parents=True)
    for pattern in ("*.py", "*.hoc"):
        for path in workdir.glob(pattern):
            shutil.copy2(path, directory / path.name)
    library = mechanism_library(workdir)
    if library is None:
        raise RuntimeError("no compiled mechanisms")
    if library.parent == workdir:  # Windows: nrnmech.dll next to the code
        shutil.copy2(library, directory / library.name)
        return
    source = library.parent.parent if library.parent.name == ".libs" else library.parent
    try:
        (directory / source.name).symlink_to(source, target_is_directory=True)
    except OSError:
        shutil.copytree(source, directory / source.name)


# ---------------------------------------------------------- calibration ----

def machine_fingerprint(cores: Cores) -> dict:
    """The hardware the best layout depends on. The host name is left out on
    purpose: it can change with the network, and identical machines share a layout."""
    return {
        "system": platform.system(),
        "arch": platform.machine(),
        "cpu": cpu_model(),
        "usable_cores": cores.usable,
        "logical_cpus": cores.logical,
    }


def _read_calibrations(workdir: Path, fingerprint: dict) -> tuple[dict, str]:
    """Calibrations for this machine, keyed by mode ("mpi" or "threads")."""
    path = workdir / CALIBRATION_FILE
    if not path.exists():
        return {}, ""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}, f"ignoring unreadable {CALIBRATION_FILE}"
    if data.get("version") != CALIBRATION_VERSION:
        return {}, f"ignoring {CALIBRATION_FILE} from an older version; run --calibrate again"
    if data.get("machine") != fingerprint:
        return {}, f"ignoring {CALIBRATION_FILE}: it was made on different hardware"
    return data.get("calibrations", {}), ""


def load_calibration(workdir: Path, fingerprint: dict, mpi: MPI | None) -> tuple[dict | None, str]:
    """The calibration for this machine and parallel mode, and a note when none applies."""
    calibrations, note = _read_calibrations(workdir, fingerprint)
    if note or not calibrations:
        return None, note
    mode = "mpi" if mpi else "threads"
    entry = calibrations.get(mode)
    if entry is None:
        flag = "" if mpi else " --no-mpi"
        return None, f"no calibration for {mode} runs yet (python run_sweep.py --calibrate{flag})"
    if mpi and entry.get("mpi") != mpi.implementation:
        return None, (f"ignoring the MPI calibration: it used {entry.get('mpi')}, "
                      f"this run uses {mpi.implementation}")
    return entry, ""


def _candidate_job_counts(cores: int) -> list[int]:
    """Concurrent-job counts to try; each fills the machine with jobs of cores // count."""
    splits = [j for j in (2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256) if j <= cores]
    widths = sorted({cores // j for j in splits} | ({1} if cores > 1 else set()), reverse=True)
    counts = [cores // width for width in widths]
    if len(counts) > 6:  # keep both extremes and an even spread
        counts = [counts[i] for i in sorted({round(k * (len(counts) - 1) / 5) for k in range(6)})]
    return counts


def _measure(layout: Layout, workdir: Path, scratch: Path, mpi: MPI | None, nrniv: str,
             cores: int, state: int, duration_ms: float) -> list[float] | None:
    """Run ``layout.jobs`` identical simulations at once; return their simulation-loop times."""
    runs = []
    for k in range(layout.jobs):
        directory = scratch / f"{layout.jobs}x{layout.ranks}x{layout.threads}-{k}"
        prepare_run_directory(directory, workdir)
        log = (directory / "run.log").open("w")
        process = subprocess.Popen(
            simulation_command(layout, mpi, nrniv, cores), cwd=directory,
            env=simulation_environment(layout, mpi, state, 1, duration_ms),
            stdout=log, stderr=subprocess.STDOUT,
        )
        runs.append((process, log, directory))
    times = []
    for process, log, directory in runs:
        code = process.wait()
        log.close()
        match = RUN_TIME.search((directory / "run.log").read_text())
        if code != 0 or not match:
            return None
        times.append(float(match.group(1)))
    return times


def calibrate(workdir: Path, cores: Cores, mpi: MPI | None, nrniv: str, state: int = 2,
              duration_ms: float = 1000.0, report: Callable[[str], None] = print) -> dict:
    """Time short simulations in candidate layouts and pick the best ones.

    ``single`` minimizes the time of one simulation; ``sweep`` maximizes the
    number of simulations finished per unit time when many are queued. Only
    the simulation loop is timed, so startup cost (negligible for full-length
    runs) does not bias the choice.
    """
    mode = "mpi" if mpi else "threads"
    usable = cores.usable
    widths = {usable, max(1, usable // 2), max(1, (3 * usable) // 4)}
    if cores.logical > usable:
        widths.add(cores.logical)  # do hyperthreads / efficiency cores help?
    candidates = [_parallel_unit(w, mpi is not None, 1) for w in sorted(widths)]
    for count in _candidate_job_counts(usable):
        unit = _parallel_unit(usable // count, mpi is not None, 1)
        candidates.append(Layout(count, unit.ranks, unit.threads))

    measurements = []
    with tempfile.TemporaryDirectory(prefix="syn-brain-calibrate-") as tmp:
        for index, layout in enumerate(candidates, start=1):
            start = time.perf_counter()
            times = _measure(layout, workdir, Path(tmp), mpi, nrniv, usable, state, duration_ms)
            elapsed = time.perf_counter() - start
            if times is None:
                report(f"  [{index}/{len(candidates)}] {layout.describe()}: failed, skipped")
                continue
            mean = sum(times) / len(times)
            throughput = layout.jobs / mean  # simulations per second of simulation loop
            measurements.append({**asdict(layout), "sim_seconds": times, "throughput": throughput})
            report(f"  [{index}/{len(candidates)}] {layout.describe()}: "
                   f"{mean:.2f} s per {duration_ms / 1000:g}-s simulation, "
                   f"{throughput * 3600:.0f} per hour ({elapsed:.0f} s)")
    if not measurements:
        raise RuntimeError("every calibration run failed; check the run logs with --dry-run")

    def layout_of(m: dict) -> Layout:
        return Layout(m["jobs"], m["ranks"], m["threads"])

    alone = [m for m in measurements if m["jobs"] == 1]
    fastest = min(m["sim_seconds"][0] for m in alone)
    single = min((m for m in alone if m["sim_seconds"][0] <= fastest * (1 + TIE_TOLERANCE)),
                 key=lambda m: layout_of(m).width)
    best = max(m["throughput"] for m in measurements)
    sweep = min((m for m in measurements if m["throughput"] >= best * (1 - TIE_TOLERANCE)),
                key=lambda m: (m["jobs"], layout_of(m).width))
    return {
        "created": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "mpi": mpi.implementation if mpi else None,
        "state": state,
        "duration_ms": duration_ms,
        "single": asdict(layout_of(single)),
        "sweep": asdict(layout_of(sweep)),
        "measurements": measurements,
    }


def save_calibration(workdir: Path, entry: dict, fingerprint: dict) -> Path:
    """Store ``entry`` for its mode, keeping this machine's calibration of the other mode."""
    calibrations, _ = _read_calibrations(workdir, fingerprint)
    calibrations[entry["mode"]] = entry
    record = {
        "version": CALIBRATION_VERSION,
        "machine": fingerprint,
        "host": socket.gethostname(),
        "calibrations": calibrations,
    }
    path = workdir / CALIBRATION_FILE
    path.write_text(json.dumps(record, indent=2) + "\n")
    return path
