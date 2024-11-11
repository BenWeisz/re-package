import os
import re
import sys
import json

from typing import Dict, List, Tuple
from enum import Enum

GREEN = "\033[32m"
YELLOW = "\033[33m"
END = "\033[0m"

class FilePattern:
    """This class represents a single file / folder matching pattern"""
    pattern: str
    include: bool
    matched: List[str]

    def __init__(self, pattern: str) -> None:
        self.pattern = pattern
        self.include = False
        self.matched = []

    def solve_pattern(self) -> None:
        """Based on self.pattern solve for all the file paths specified the pattern"""
        
        # Calculate the include type
        if self.pattern[0] == "+":
            self.include = True 
        elif self.pattern[0] == "-":
            self.include = False
        else:
            print("Missing +/-, skipping pattern")

        self.pattern = self.pattern[1:]

        file_regex = r"^[\w,\s-]+\.[A-Za-z]+$"
        is_file = re.search(file_regex, os.path.basename(self.pattern))
        if not is_file:
            # Handle folder type patterns
            for root, _, files in os.walk(f".{self.pattern}", topdown=False):
                self.matched.extend([os.path.join(root, name) for name in files])
        else:
            # Handle file type patterns
            self.matched.append(f".{self.pattern}")

def solve_file_patterns(config: Dict) -> List[FilePattern]:
    """Return a list of FilePattern's based on the config file"""
    
    # Change to root directory
    os.chdir(config["root"])

    # Solve the file patterns for the individual patterns in the config file
    file_patterns = []
    for pattern in config["patterns"]:
        file_pattern = FilePattern(pattern)
        file_pattern.solve_pattern()
        file_patterns.append(file_pattern)
    
    return file_patterns

class CodeFileType(Enum):
    UNKNOWN = 0
    SOURCE = 1
    HEADER = 2


class CodeFile:
    """A class to represent a file among the files to be bundled"""
    type: CodeFileType
    name: str
    parent: str
    path: str

    contents: List[str]
    dependencies = List[str]

    def __init__(self, path: str, source_types: List[str], header_types: List[str]) -> None:
        self.name = os.path.basename(path)
        self.parent = os.path.dirname(path) + "/"
        self.path = path

        if any([self.name.endswith(ext) for ext in source_types]):
            self.type = CodeFileType.SOURCE
        elif any([self.name.endswith(ext) for ext in header_types]):
            self.type = CodeFileType.HEADER
        else:
            self.type = CodeFileType.UNKNOWN

        # Read the file contents
        with open(path, "r") as in_file:
            self.contents = in_file.readlines()

        self.dependencies = []
        self.resolve_dependencies()

    def resolve_dependencies(self) -> None:
        """Parse through this CodeFile's self.contents looking for #include's that use "" marks.
           These are assumed to be paths to internal headers that this function will resolve to 
           CodeFile instances from code_files. We do this because we have to topological sort on
           the CodeFiles to see which ones we must past into the output first.
        """

        # Capture the file names for each of the include directive files relative to the config root
        pattern = r'#include\s+"(.+?)"'
        line_indices_to_delete = []
        for line_i, line in enumerate(self.contents):
            match = re.match(pattern, line)
            if match:
                include_path = match.group(1) # Extract the include path from the #include "../path/file.h" directive
                norm_include_path = "./" + os.path.normpath(self.parent + include_path)
                self.dependencies.append(norm_include_path)
                line_indices_to_delete = [line_i] + line_indices_to_delete
        
        for line_i in line_indices_to_delete:
            del self.contents[line_i]

    def __repr__(self) -> str:
        return self.path

def collect_code_files(config: Dict) -> List[CodeFile]:
    """Get all of the code files specified by config"""
    file_patterns = solve_file_patterns(config)

    file_paths = []
    for file_pattern in file_patterns:
        if file_pattern.include:
            # + type patterns
            file_paths.extend(file_pattern.matched)
        else:
            # - type patterns
            file_paths = list(filter(lambda path: path not in file_pattern.matched, file_paths))

    code_files = []
    print("Loading Files ...")
    for file_path_i, file_path in enumerate(file_paths):
        print("Loading Progress: [" + GREEN + str(file_path_i + 1) + END + "/" + GREEN + str(len(file_paths)) + END + "]", end="\r")
        code_file = CodeFile(file_path, config["source-extensions"], config["header-extensions"])
    
        if code_file.type == CodeFileType.UNKNOWN:
            print(YELLOW + f"Unknown file type: " + END + f"{code_file.path}")
            continue

        code_files.append(code_file)
    print("")

    return code_files

def topo_sort_code_files(code_files: List[CodeFile]) -> Tuple[List[CodeFile], List[CodeFile]]:
    """Perform a topological sorting of the CodeFile instances."""

    source_code_files = list(filter(lambda code_file: code_file.type == CodeFileType.SOURCE, code_files))
    header_code_files = list(filter(lambda code_file: code_file.type == CodeFileType.HEADER, code_files))
    
    header_code_files_len = len(header_code_files)

    top_sorted_code_files = []
    while len(header_code_files) > 0:
        print("Topo-sort pass on headers: [" + 
              GREEN + f"{header_code_files_len - len(header_code_files) + 1}" + 
              END + "/" + GREEN + f"{header_code_files_len}" + END + "]", end="\r")
        min_index = 0
        min_element = 100000
        for element_i, element in enumerate(header_code_files):
            if len(element.dependencies) < min_element:
                min_index = element_i
                min_element = len(element.dependencies)
        
        min_code_file = header_code_files[min_index]
        top_sorted_code_files.append(min_code_file)

        for element in header_code_files:
            element_i = -1
            for dependent_i, dependent in enumerate(element.dependencies):
                if dependent == min_code_file.path:
                    element_i = dependent_i
            if element_i != -1:
                del element.dependencies[element_i]

        del header_code_files[min_index]
    print("")

    return top_sorted_code_files, source_code_files

def assemble_uber_file(config: Dict, header_code_files: List[CodeFile], source_code_files: List[CodeFile]) -> List[str]:
    """Assemble the uber list of code lines from the header and source code files."""
    uber_lines = []

    print("Assembling code files ...")

    # Add the header file lines
    for header_code_file in header_code_files:
        uber_lines.extend(header_code_file.contents)
        uber_lines.append("\n")

    uber_name = config["name"].upper()
    uber_lines.append(f"#ifdef {uber_name}_IMPLEMENTATION\n")
    
    # Add the source file lines
    for source_code_file in source_code_files:
        uber_lines.extend(source_code_file.contents)
        uber_lines.append("\n")

    uber_lines.append(f"#endif //{uber_name}_IMPLEMENTATION\n")

    return uber_lines

def create_uber_file(config: Dict) -> None:
    """Create uber file and write it out to disk."""


    # Collect all of the code files and their contents / dependencies
    code_files = collect_code_files(config)

    # Sort the code files based on their dependencies
    header_code_files, source_code_files = topo_sort_code_files(code_files)

    print("Creating uber file ...")
    
    # Assemble the uber file lines
    uber_lines = assemble_uber_file(config, header_code_files, source_code_files)
    
    # Write out the uber file
    name = config["name"] + ".h"
    with open(name, "w") as out_file:
        for line in uber_lines:
            out_file.write(line)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Please call the re-pacakage as follows:\n\tpython re-pacakage.py config.json\n\nSee /templates for examples of config.json files")
        exit()

    # Load the config file
    with open(sys.argv[1], "r") as in_file:
        config = json.load(in_file)

    # Create the uber files
    create_uber_file(config)
    print(f"Completed: Output written to {config["root"]}/{config["name"]}.h")
    