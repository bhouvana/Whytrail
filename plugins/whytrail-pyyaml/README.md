# whytrail-pyyaml

`why()` on a `yaml.MarkedYAMLError` (`ParserError`, `ScannerError`,
`ConstructorError`, ...) shows the file/line/column, with the parser's
problem description and a document snippet available via the redactable
`locals` mechanism used throughout this ecosystem (ADR 0002 §3 item 5).

```python
try:
    yaml.safe_load(config_text)
except yaml.MarkedYAMLError as exc:
    print(whytrail.why(exc))
```

**No part of the document is ever used in `description`.** PyYAML parses
config files as often as data files, and both the snippet *and*
`.problem` (which, for `ConstructorError`, embeds the actual tag string
from the document) can carry real content -- so `description` is built
only from the exception type and location; everything else goes through
`locals`. Call `.redacted()` before sending an `Explanation` anywhere
off-box.
