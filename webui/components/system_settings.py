import streamlit as st

from app.utils import utils
from webui.services.system_actions import clear_directory, get_workspace_layout_rows
from webui.utils import local_api_client


def _render_clear_result(result, tr):
    status, message = result
    translated = tr(message) if message in {"Directory cleared", "Directory does not exist"} else message
    if status == "success":
        st.success(translated)
    elif status == "warning":
        st.warning(translated)
    else:
        st.error(translated)


def render_system_panel(tr):
    with st.expander(tr("System settings"), expanded=False):
        st.caption(f"Workspace: {utils.workspace_dir()}")
        st.caption(f"Local API: {local_api_client.get_local_api_base_url()}")
        with st.container(border=True):
            st.caption(tr("Workspace layout"))
            for relative_path, absolute_path in get_workspace_layout_rows():
                st.caption(f"{relative_path}: {absolute_path}")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button(tr("Clear temp"), use_container_width=True):
                _render_clear_result(clear_directory(utils.temp_dir()), tr)

        with col2:
            if st.button(tr("Clear cache"), use_container_width=True):
                _render_clear_result(clear_directory(utils.cache_dir()), tr)

        with col3:
            if st.button(tr("Clear tasks"), use_container_width=True):
                _render_clear_result(clear_directory(utils.task_dir()), tr)
