"""util.py - General utilities for running, loading, and processing benchmarks"""

import json
import os
import re
import subprocess
import sys
import tempfile

# Input file type enumeration
IT_Invalid = 0
IT_JSON = 1
IT_Executable = 2

_num_magic_bytes = 2 if sys.platform.startswith("win") else 4


def is_executable_file(filename):
    """
    Return 'True' if 'filename' names a valid file which is likely
    an executable. A file is considered an executable if it starts with the
    magic bytes for a EXE, Mach O, or ELF file.
    """
    if not os.path.isfile(filename):
        return False
    with open(filename, mode="rb") as f:
        magic_bytes = f.read(_num_magic_bytes)
    if sys.platform == "darwin":
        return magic_bytes in [
            b"\xfe\xed\xfa\xce",  # MH_MAGIC
            b"\xce\xfa\xed\xfe",  # MH_CIGAM
            b"\xfe\xed\xfa\xcf",  # MH_MAGIC_64
            b"\xcf\xfa\xed\xfe",  # MH_CIGAM_64
            b"\xca\xfe\xba\xbe",  # FAT_MAGIC
            b"\xbe\xba\xfe\xca",  # FAT_CIGAM
        ]
    elif sys.platform.startswith("win"):
        return magic_bytes == b"MZ"
    else:
        return magic_bytes == b"\x7fELF"


def is_json_file(filename):
    """
    Returns 'True' if 'filename' names a valid JSON output file.
    'False' otherwise.
    """
    try:
        with open(filename, "r") as f:
            json.load(f)
        return True
    except BaseException:
        pass
    return False


def classify_input_file(filename):
    """
    Return a tuple (type, msg) where 'type' specifies the classified type
    of 'filename'. If 'type' is 'IT_Invalid' then 'msg' is a human readable
    string representing the error.
    """
    ftype = IT_Invalid
    err_msg = None
    if not os.path.exists(filename):
        err_msg = "'%s' does not exist" % filename
    elif not os.path.isfile(filename):
        err_msg = "'%s' does not name a file" % filename
    elif is_executable_file(filename):
        ftype = IT_Executable
    elif is_json_file(filename):
        ftype = IT_JSON
    else:
        err_msg = (
            "'%s' does not name a valid benchmark executable or JSON file"
            % filename
        )
    return ftype, err_msg


def check_input_file(filename):
    """
    Classify the file named by 'filename' and return the classification.
    If the file is classified as 'IT_Invalid' print an error message and exit
    the program.
    """
    ftype, msg = classify_input_file(filename)
    if ftype == IT_Invalid:
        print("Invalid input file: %s" % msg)
        sys.exit(1)
    return ftype


def find_benchmark_flag(prefix, benchmark_flags):
    """
    Search the specified list of flags for a flag matching `<prefix><arg>` and
    if it is found return the arg it specifies. If specified more than once the
    last value is returned. If the flag is not found None is returned.
    """
    assert prefix.startswith("--") and prefix.endswith("=")
    result = None
    for f in benchmark_flags:
        if f.startswith(prefix):
            result = f[len(prefix) :]
    return result


def remove_benchmark_flags(prefix, benchmark_flags):
    """
    Return a new list containing the specified benchmark_flags except those
    with the specified prefix.
    """
    assert prefix.startswith("--") and prefix.endswith("=")
    return [f for f in benchmark_flags if not f.startswith(prefix)]


def load_benchmark_results(fname, benchmark_filter):
    """
    Read benchmark output from a file and return the JSON object.

    Apply benchmark_filter, a regular expression, with nearly the same
    semantics of the --benchmark_filter argument.  May be None.
    Note: the Python regular expression engine is used instead of the
    one used by the C++ code, which may produce different results
    in complex cases.

    REQUIRES: 'fname' names a file containing JSON benchmark output.
    """

    def benchmark_wanted(benchmark):
        if benchmark_filter is None:
            return True
        name = benchmark.get("run_name", None) or benchmark["name"]
        return re.search(benchmark_filter, name) is not None

    with open(fname, "r") as f:
        results = json.load(f)
        if "context" in results:
            if "json_schema_version" in results["context"]:
                json_schema_version = results["context"]["json_schema_version"]
                if json_schema_version != 1:
                    print(
                        "In %s, got unnsupported JSON schema version: %i, expected 1"
                        % (fname, json_schema_version)
                    )
                    sys.exit(1)
        if "benchmarks" in results:
            results["benchmarks"] = list(
                filter(benchmark_wanted, results["benchmarks"])
            )
        return results


def sort_benchmark_results(result):
    benchmarks = result["benchmarks"]

    # From inner key to the outer key!
    benchmarks = sorted(
        benchmarks,
        key=lambda benchmark: benchmark["repetition_index"]
        if "repetition_index" in benchmark
        else -1,
    )
    benchmarks = sorted(
        benchmarks,
        key=lambda benchmark: 1
        if "run_type" in benchmark and benchmark["run_type"] == "aggregate"
        else 0,
    )
    benchmarks = sorted(
        benchmarks,
        key=lambda benchmark: benchmark["per_family_instance_index"]
        if "per_family_instance_index" in benchmark
        else -1,
    )
    benchmarks = sorted(
        benchmarks,
        key=lambda benchmark: benchmark["family_index"]
        if "family_index" in benchmark
        else -1,
    )

    result["benchmarks"] = benchmarks
    return result


def run_benchmark(exe_name, benchmark_flags):
    """
    Run a benchmark specified by 'exe_name' with the specified
    'benchmark_flags'. The benchmark is run directly as a subprocess to preserve
    real time console output.
    RETURNS: A JSON object representing the benchmark output
    """
    output_name = find_benchmark_flag("--benchmark_out=", benchmark_flags)
    is_temp_output = False
    if output_name is None:
        is_temp_output = True
        thandle, output_name = tempfile.mkstemp()
        os.close(thandle)
        benchmark_flags = list(benchmark_flags) + [
            "--benchmark_out=%s" % output_name
        ]

    cmd = [exe_name] + benchmark_flags
    print("RUNNING: %s" % " ".join(cmd))
    exitCode = subprocess.call(cmd)
    if exitCode != 0:
        print("TEST FAILED...")
        sys.exit(exitCode)
    json_res = load_benchmark_results(output_name, None)
    if is_temp_output:
        os.unlink(output_name)
    return json_res


def run_or_load_benchmark(filename, benchmark_flags):
    """
    Get the results for a specified benchmark. If 'filename' specifies
    an executable benchmark then the results are generated by running the
    benchmark. Otherwise 'filename' must name a valid JSON output file,
    which is loaded and the result returned.
    """
    ftype = check_input_file(filename)
    if ftype == IT_JSON:
        benchmark_filter = find_benchmark_flag(
            "--benchmark_filter=", benchmark_flags
        )
        return load_benchmark_results(filename, benchmark_filter)
    if ftype == IT_Executable:
        return run_benchmark(filename, benchmark_flags)
    raise ValueError("Unknown file type %s" % ftype)
