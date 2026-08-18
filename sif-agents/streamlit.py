"""Entrypoint / router for the sif-agents Streamlit app.

This file is what OOD's `template/script.sh.erb` (and a local
`streamlit run streamlit.py`) launches. Its only job is to define the
navigation menu with `st.navigation`/`st.Page` and hand off to whichever page
the user selected -- per Streamlit's own docs, this file "acts like a router
or frame of common elements around each of your pages" and is re-executed on
every rerun, so `st.set_page_config` belongs here (once), not in the pages.

Deliberately explicit rather than relying on Streamlit's automatic `pages/`
directory discovery: that auto-discovery re-scans the pages/ directory using
a filesystem watcher, which doesn't reliably notice new files added to a
network filesystem like /scratch in an already-running session -- a page
added after the server started stayed invisible until this rewrite. Calling
`st.navigation` explicitly means the page list is read fresh on every script
run instead of depending on file-watch events at all.
"""

from __future__ import annotations

import os
import sys

# This file is named streamlit.py, which shadows the real `streamlit` package
# the moment its own directory is on sys.path (Streamlit's launcher, like a
# plain `python streamlit.py`, prepends the script's directory to sys.path) --
# `import streamlit` would otherwise import this very file instead of the
# installed package. Strip that entry before importing, then restore it for
# this project's own imports below (and so it's still present for any code
# path that runs before a routed page's own guard does the same thing).
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path = [p for p in sys.path if os.path.abspath(p or ".") != _HERE]

import streamlit as st

sys.path.insert(0, _HERE)

st.set_page_config(page_title="sif-agents", layout="wide")

pages = st.navigation(
    [
        st.Page("pages/run_pipeline.py", title="Run Pipeline", icon="🧬", default=True),
        st.Page("pages/results_gallery.py", title="Results Gallery", icon="🧪"),
        st.Page("pages/browse_files.py", title="Browse Files", icon="📁"),
    ]
)
pages.run()
