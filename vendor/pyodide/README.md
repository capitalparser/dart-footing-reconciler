# PyOdide runtime assets

Vendored PyOdide assets are not stored in this repository.

Pin: PyOdide 0.26.4

Download and extract the runtime into this directory before running the offline app:

```bash
mkdir -p vendor/pyodide
curl -L -o /tmp/pyodide-0.26.4.tar.bz2 \
  https://github.com/pyodide/pyodide/releases/download/0.26.4/pyodide-0.26.4.tar.bz2
tar -xjf /tmp/pyodide-0.26.4.tar.bz2 -C vendor/pyodide --strip-components=1
```

The app loads local files only at runtime and expects packages:
`micropip`, `lxml`, `beautifulsoup4`, and `openpyxl`.
