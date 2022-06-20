import atexit
import dis
import linecache
import os
import runpy
import sys
from types import CodeType, FunctionType

from bytecode import ConcreteBytecode, Instr
from rich import print
from rich.columns import Columns
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax

_TRACED_CODE: dict[CodeType, list[tuple[int, int, int]]] = {}


def unwind(frame):
    stack = []
    while frame:
        stack.append(frame)
        frame = frame.f_back

    return "\n".join(
        f"{frame.f_code.co_name} ({frame.f_code.co_filename})"
        for frame in reversed(stack)
    )


def realign(code: CodeType, recursive: bool = False) -> CodeType:
    if code in _TRACED_CODE:
        return code

    bytecode = ConcreteBytecode.from_code(code)

    for n, i in enumerate((_ for _ in bytecode if isinstance(_, Instr))):
        i._lineno = i.lineno
        i.lineno = n + 1

    if recursive:
        for i, o in enumerate(bytecode.consts):
            if isinstance(o, CodeType):
                bytecode.consts[i] = realign(o)

    _TRACED_CODE[code] = list(code.co_lines())
    return bytecode.to_code()


runpy_run_code = runpy._run_code


def _run_code(code, *args, **kwargs):
    for o in code.co_consts:
        if isinstance(o, FunctionType):
            o.__code__ = realign(o.__code__)
    runpy_run_code(realign(code, recursive=True), *args, **kwargs)


runpy._run_code = _run_code
atexit.register(lambda: setattr(runpy, "_run_code", runpy_run_code))


def tracer(frame, event, arg):
    if event not in {"line", "return"} or frame.f_code not in _TRACED_CODE:
        return tracer

    code = frame.f_code

    _locals = dict(frame.f_locals)
    if event == "return":
        _locals["@return"] = arg

    os.system("clear")

    w, _ = os.get_terminal_size()

    code_height = 11

    instrs = list(dis.get_instructions(code))

    index = frame.f_lasti >> 1

    before = min(max(0, index - code_height // 2), len(instrs) - code_height)
    after = code_height + before

    lines = _TRACED_CODE[code]
    for s, e, l in lines:
        if s <= frame.f_lasti <= e:
            break

    first_line = max(1, min(l - 2, max(l for _, _, l in lines) - 5))
    last_line = 5 + first_line

    source = Syntax(
        "".join(
            (
                linecache.getline(frame.f_code.co_filename, _)
                for _ in range(first_line, last_line + 1)
            )
        ),
        "python",
        line_numbers=True,
        start_line=first_line,
        highlight_lines=[l],
    )

    # Rendering logic below

    print(Panel(unwind(frame), title="Frame stack"))

    for i, ins in enumerate(instrs):
        if before <= i < after:
            iarg = f"{ins.arg} ({ins.argval})" if ins.argval is not None else ""
            prefix = "[b]--> " if i == index else "    "
            print(f"{prefix}{ins.opname:30s}{iarg[:w-34]}")

    print(Panel(source, title="Source", subtitle=frame.f_code.co_filename))

    print(
        Panel(
            Columns(
                [f"{k} = {repr(v)}" for k, v in _locals.items()],
                equal=True,
                expand=True,
            ),
            title="Locals",
        )
    )

    # Evaluate user input
    while True:
        try:
            command = input(">>> ")
        except KeyboardInterrupt:
            print()
            interrupt = Prompt.ask(
                "Are you sure you want to interrupt the execution?",
                choices=["y", "n"],
                default="y",
            )
            if interrupt == "y":
                exit()
            continue
        if not command:
            break
        try:
            print(repr(eval(command, globals(), _locals)))
        except Exception as e:
            print(e)

    return tracer


old_trace = sys.gettrace()
sys.settrace(tracer)
atexit.register(lambda: sys.settrace(old_trace))
