import argparse
import os
import site
from distutils import spawn


def main():
    parser = argparse.ArgumentParser(
        prog="podb",
        usage="podb python -m <module> [<args>]",
    )
    parser.add_argument(
        "command", nargs=argparse.REMAINDER, type=str, help="Command string to execute."
    )
    args = parser.parse_args()

    python_paths = os.environ.get("PYTHONPATH", "").split(os.path.pathsep)
    python_paths.insert(0, os.path.join(os.path.dirname(__file__), "bootstrap"))
    python_paths.extend(site.getsitepackages())

    os.environ["PYTHONPATH"] = os.path.pathsep.join(python_paths)

    executable = spawn.find_executable(args.command[0])
    os.execl(executable, executable, *args.command[1:])


if __name__ == "__main__":
    main()
