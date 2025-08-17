# C## (C‑sharp‑sharp) — toy language
An **educational programming language** that blends a tiny C++/C#-like syntax and executes on a lightweight interpreter written in Python.

> ⚠️ This is a toy for learning. It implements a compact subset: variables, functions, control flow, lists, `Console.WriteLine`, and a few C#-style niceties (`foreach`, `var`, `List<T>`). No real static typing yet.

## Features (v0.2)
- Variables: `var x = 10;` or `int x = 10;` (type is not enforced yet).
- Functions: `int Main() { ... }`, user functions with parameters.
- Control flow: `if / else`, `while`, `for`, `foreach (var x in xs) { ... }`.
- Expressions: `+ - * / %`, comparisons, logical `&& || !`, indexing `xs[i]`.
- Built-ins: `Console.WriteLine(...)`, `Console.ReadLine()`.
- Lists: `List<int> xs = List(); xs.push_back(1); xs[0]; xs.size();`.
- Namespaces are parsed but currently ignored at runtime.
- REPL: `python3 src/cshs.py repl`

## Install & Run
Requires Python 3.9+.
```bash
python3 src/cshs.py run examples/hello.c##
python3 src/cshs.py run examples/list_demo.c##
python3 src/cshs.py repl
python3 src/cshs.py ast examples/hello.c##
```

## Makefile shortcuts
```bash
make hello
make list
make fib
```

## Language sketch
```c
using System;

int Square(int x) { return x * x; }

int Main() {
  var xs = List();
  for (var i = 0; i < 5; i = i + 1) { xs.push_back(i); }

  foreach (var n in xs) {
    Console.WriteLine(Square(n));
  }

  if (xs.size() > 3) {
    Console.WriteLine("big");
  } else {
    Console.WriteLine("small");
  }
  return 0;
}
```

## Folder layout
```
CsharpSharp_full/
├── LICENSE
├── Makefile
├── README.md
├── editors
│   └── vscode
│       └── cshs-syntax.json
├── examples
│   ├── control_flow.c##
│   ├── fib.c##
│   ├── hello.c##
│   └── list_demo.c##
├── src
│   └── cshs.py
├── stdlib
│   ├── console.csstd
│   └── list.csstd
└── tests
    ├── math.c##
    └── strings.c##
```

## License
MIT (see `LICENSE`).
