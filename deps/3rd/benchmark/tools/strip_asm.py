#!/usr/bin/env python3

"""
strip_asm.py - Cleanup ASM output for the specified file
"""

import os
import re
import sys
from argparse import ArgumentParser


def find_used_labels(asm):
    found = set()
    label_re = re.compile(r"\s*j[a-z]+\s+\.L([a-zA-Z0-9][a-zA-Z0-9_]*)")
    for line in asm.splitlines():
        m = label_re.match(line)
        if m:
            found.add(".L%s" % m.group(1))
    return found


def normalize_labels(asm):
    decls = set()
    label_decl = re.compile("^[.]{0,1}L([a-zA-Z0-9][a-zA-Z0-9_]*)(?=:)")
    for line in asm.splitlines():
        m = label_decl.match(line)
        if m:
            decls.add(m.group(0))
    if len(decls) == 0:
        return asm
    needs_dot = next(iter(decls))[0] != "."
    if not needs_dot:
        return asm
    for ld in decls:
        asm = re.sub(r"(^|\s+)" + ld + r"(?=:|\s)", "\\1." + ld, asm)
    return asm


def transform_labels(asm):
    asm = normalize_labels(asm)
    used_decls = find_used_labels(asm)
    new_asm = ""
    label_decl = re.compile(r"^\.L([a-zA-Z0-9][a-zA-Z0-9_]*)(?=:)")
    for line in asm.splitlines():
        m = label_decl.match(line)
        if not m or m.group(0) in used_decls:
            new_asm += line
            new_asm += "\n"
    return new_asm


def is_identifier(tk):
    if len(tk) == 0:
        return False
    first = tk[0]
    if not first.isalpha() and first != "_":
        return False
    for i in range(1, len(tk)):
        c = tk[i]
        if not c.isalnum() and c != "_":
            return False
    return True


def process_identifiers(line):
    """
    process_identifiers - process all identifiers and modify them to have
    consistent names across all platforms; specifically across ELF and MachO.
    For example, MachO inserts an additional understore at the beginning of
    names. This function removes that.
    """
    parts = re.split(r"([a-zA-Z0-9_]+)", line)
    new_line = ""
    for tk in parts:
        if is_identifier(tk):
            if tk.startswith("__Z"):
                tk = tk[1:]
            elif (
                tk.startswith("_")
                and len(tk) > 1
                and tk[1].isalpha()
                and tk[1] != "Z"
            ):
                tk = tk[1:]
        new_line += tk
    return new_line


def process_asm(asm):
    """
    Strip the ASM of unwanted directives and lines
    """
    new_contents = ""
    asm = transform_labels(asm)

    # TODO: Add more things we want to remove
    discard_regexes = [
        re.compile(r"\s+\..*$"),  # directive
        re.compile(r"\s*#(NO_APP|APP)$"),  # inline ASM
        re.compile(r"\s*#.*$"),  # comment line
        re.compile(
            r"\s*\.globa?l\s*([.a-zA-Z_][a-zA-Z0-9$_.]*)"
        ),  # global directive
        re.compile(
            r"\s*\.(string|asciz|ascii|[1248]?byte|short|word|long|quad|value|zero)"
        ),
    ]
    keep_regexes: list[re.Pattern] = []
    fn_label_def = re.compile("^[a-zA-Z_][a-zA-Z0-9_.]*:")
    for line in asm.splitlines():
        # Remove Mach-O attribute
        line = line.replace("@GOTPCREL", "")
        add_line = True
        for reg in discard_regexes:
            if reg.match(line) is not None:
                add_line = False
                break
        for reg in keep_regexes:
            if reg.match(line) is not None:
                add_line = True
                break
        if add_line:
            if fn_label_def.match(line) and len(new_contents) != 0:
                new_contents += "\n"
            line = process_identifiers(line)
            new_contents += line
            new_contents += "\n"
    return new_contents


def main():
    parser = ArgumentParser(description="generate a stripped assembly file")
    parser.add_argument(
        "input",
        metavar="input",
        type=str,
        nargs=1,
        help="An input assembly file",
    )
    parser.add_argument(
        "out", metavar="output", type=str, nargs=1, help="The output file"
    )
    args, unknown_args = parser.parse_known_args()
    input = args.input[0]
    output = args.out[0]
    if not os.path.isfile(input):
        print("ERROR: input file '%s' does not exist" % input)
        sys.exit(1)

    with open(input, "r") as f:
        contents = f.read()
    new_contents = process_asm(contents)
    with open(output, "w") as f:
        f.write(new_contents)


if __name__ == "__main__":
    main()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
# kate: tab-width: 4; replace-tabs on; indent-width 4; tab-indents: off;
# kate: indent-mode python; remove-trailing-spaces modified;
