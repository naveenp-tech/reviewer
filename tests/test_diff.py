from app.diff import parse_unified_diff

SAMPLE = '''diff --git a/app/x.py b/app/x.py
index 1111111..2222222 100644
--- a/app/x.py
+++ b/app/x.py
@@ -1,3 +1,4 @@
 import os
-x = 1
+x = 2
+eval("1+1")
@@ -10,2 +11,3 @@
 def f():
     pass
+    return 1
'''

NEW_FILE = '''diff --git a/new.py b/new.py
new file mode 100644
--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+print(1)
+print(2)
'''


def test_parses_added_lines_with_new_line_numbers():
    files = parse_unified_diff(SAMPLE)
    assert len(files) == 1
    assert files[0].path == "app/x.py"
    assert files[0].added == [
        (2, "x = 2"),
        (3, 'eval("1+1")'),
        (13, "    return 1"),
    ]


def test_new_file_uses_dev_null():
    files = parse_unified_diff(NEW_FILE)
    assert len(files) == 1
    assert files[0].path == "new.py"
    assert [line for line, _ in files[0].added] == [1, 2]


def test_removed_lines_are_ignored():
    diff = """--- a/x.py
+++ b/x.py
@@ -1,2 +1,1 @@
-removed()
 keep()
"""
    files = parse_unified_diff(diff)
    assert files == []


def test_non_diff_text_returns_nothing():
    assert parse_unified_diff("just some prose") == []
