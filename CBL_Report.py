import streamlit as st
import plotly.io as pio
from pathlib import Path
import json
from datetime import datetime
from typing import List, Tuple, Any, Callable, Optional
import asyncio
import logging


# Configure logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# Set Streamlit page configuration
st.set_page_config(layout="wide")

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            img[data-testid="appCreatorAvatar"] {display: none !important;}
            div._link_gzau3_10 {display: none !important;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

DEFAULT_PAGE_SIZE = 10

def get_page_prefix(chart_dir: Path) -> str:
    """Generates a unique page prefix based on chart directory."""
    return f"page_{chart_dir.as_posix().replace('/', '_')}_"

def init_session_state(page_prefix: str) -> None:
    """Initializes session state variables for a given page."""
    SESSION_STATE_VARS = {
        "search_query": "",
        "selected_types": [],
        "page_number": 0,
        "sort_by": "Size",
        "page_size": DEFAULT_PAGE_SIZE,
        "all_files": [],
        "selected_chart": None,
        "loading": False,
        "error": None,
        "filtered_files": [],
        "use_async": False,
        "loading_all_charts": False
    }
    for key, default_value in SESSION_STATE_VARS.items():
        if f"{page_prefix}{key}" not in st.session_state:
            st.session_state[f"{page_prefix}{key}"] = default_value

def update_session_state(page_prefix: str, key: str, value: Any) -> None:
    """Updates the session state with page prefix."""
    st.session_state[f"{page_prefix}{key}"] = value

def clear_error(page_prefix: str) -> None:
    """Clears the current error state."""
    update_session_state(page_prefix, "error", None)

def handle_error(page_prefix: str, error_message: str, error_type: str = "error") -> None:
    """Handles setting error state and displaying a custom error message."""
    update_session_state(page_prefix, "error", error_message)
    if error_type == "error":
        st.markdown(
            f"""
            <div style="background-color:#ffe8e8; padding:1em; border-radius:5px; margin-top:1em; margin-bottom: 1em;">
            <span style="color:#ff0000; font-weight:bold;">⚠️ Error:</span> {error_message}
            </div>
            """, unsafe_allow_html=True
        )
        logging.error(f"Error: {error_message}")  # Log the error
    elif error_type == "warning":
        st.warning(error_message, icon="⚠️")
    elif error_type == "info":
        st.info(error_message, icon="ℹ️")
    else:
        st.markdown(
            f"""
                <div style="background-color:#e8f0ff; padding:1em; border-radius:5px; margin-top:1em; margin-bottom: 1em;">
                  {error_message}
                </div>
             """, unsafe_allow_html=True
        )
        logging.info(f"Info: {error_message}")  # Log the info message


@st.cache_data(ttl=3600, max_entries=10)
def load_figure_json(json_file: Path) -> str:
    """Loads a Plotly figure from a JSON file and returns the json str."""
    try:
        with open(json_file, "r") as f:
            fig_json = f.read()
            if not fig_json:
                raise ValueError(f"Empty JSON file: {json_file.name}")
            return fig_json
    except FileNotFoundError:
        raise FileNotFoundError(f"Chart file not found at: {json_file.name}")
    except json.JSONDecodeError:
        raise json.JSONDecodeError(f"Could not decode chart at {json_file.name}. Please check if the file is valid JSON", "", 0)
    except Exception as e:
       raise Exception(f"An unexpected error occurred loading chart {json_file.name}: {e}")

async def load_figure_json_async(json_file: Path) -> str:
    """Loads a Plotly figure from a JSON file asynchronously and returns the json str."""
    try:
        loop = asyncio.get_event_loop()
        with open(json_file, "r") as f:
            fig_json = await loop.run_in_executor(None, f.read) # use the event loop to load asynchronously
            if not fig_json:
                raise ValueError(f"Empty JSON file: {json_file.name}")
            return fig_json
    except FileNotFoundError:
        raise FileNotFoundError(f"Chart file not found at: {json_file.name}")
    except json.JSONDecodeError:
        raise json.JSONDecodeError(f"Could not decode chart at {json_file.name}. Please check if the file is valid JSON", "", 0)
    except Exception as e:
       raise Exception(f"An unexpected error occurred loading chart {json_file.name}: {e}")

def get_file_metadata(file_path: Path) -> Tuple[str, str, int, str]:
    """Extracts metadata from a file path and returns as a tuple."""
    try:
        stat = file_path.stat()
        return (
            file_path.name,
            datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            stat.st_size,
            str(file_path),
        )
    except FileNotFoundError:
        return (file_path.name, "N/A", 0, str(file_path))
    except Exception as e:
        raise Exception(f"Error getting metadata for {file_path.name}: {e}")


async def display_chart(page_prefix: str, chart_metadata: Tuple[str, str, int, str], chart_height: int, use_async: bool = False) -> None:
    """Displays a single chart."""
    if not chart_metadata or not chart_metadata[3]:
        handle_error(page_prefix, "Invalid chart metadata provided or file path missing")
        return

    chart_path = Path(chart_metadata[3])
    with st.spinner(f"Loading {chart_metadata[0]}..."):
       try:
            if use_async:
                fig_json = await load_figure_json_async(chart_path) # Change asyncio.run to await
            else:
                fig_json = load_figure_json(chart_path)
            fig = pio.from_json(fig_json) # create the figure
            if fig:
                fig.update_layout(height=chart_height)
                st.plotly_chart(fig, use_container_width=True, key=chart_metadata[0])
       except Exception as e:
         handle_error(page_prefix, f"Error displaying chart {chart_metadata[0]}: {e}")

def get_all_json_files(directory: Path) -> List[Path]:
    """Retrieves all JSON file paths from the directory."""
    if not directory.exists() or not directory.is_dir():
         handle_error(get_page_prefix(directory), f"Directory not found at: {directory}", error_type="error")
         return []
    try:
        return [f for f in directory.glob("*.json")]
    except Exception as e:
        handle_error(get_page_prefix(directory), f"Error getting JSON files: {e}", error_type="error")
        return []

SORT_KEYS = {
    "Name": lambda x: x[0].lower(),
    "Last Modified": lambda x: x[1],
    "Size": lambda x: x[2],
}

def sort_files(files: List[Tuple[str, str, int, str]], sort_by: str) -> List[Tuple[str, str, int, str]]:
    """Sorts files based on the selected attribute."""
    try:
        return sorted(files, key=SORT_KEYS.get(sort_by), reverse=sort_by != "Name")
    except KeyError:
        handle_error(get_page_prefix(Path("")), f"Invalid sort key: {sort_by}. Using default sorting.", error_type="warning")
        return files # Return original files to prevent app from breaking

def filter_charts(files_metadata: List[Tuple[str, str, int, str]], search_query: str, selected_types: List[str]) -> List[Tuple[str, str, int, str]]:
    """Filters charts based on search query and selected types."""
    search_term = search_query.lower() if search_query else ""

    if not search_term and not selected_types:
        return files_metadata

    return [
        f
        for f in files_metadata
        if search_term in f[0].lower()
        and (not selected_types or any(t in f[0] for t in selected_types))
    ]

def display_metadata(chart_metadata: Tuple[str, str, int, str]) -> None:
    """Displays metadata for a chart."""
    st.markdown(
        f"""
        #### {chart_metadata[0]}
        Last Modified: {chart_metadata[1]} | Size: {chart_metadata[2]} bytes
    """,
        unsafe_allow_html=True,
    )

async def display_all_charts(page_prefix: str, filtered_files: List[Tuple[str, str, int, str]], chart_height: int, use_async: bool = False) -> None:
    """Displays all charts on the page."""
    try:
        if not filtered_files:
            handle_error(page_prefix, "No charts to display", error_type="info")
            return

        start_index = st.session_state[f"{page_prefix}page_number"] * st.session_state[f"{page_prefix}page_size"]
        end_index = min(
            (st.session_state[f"{page_prefix}page_number"] + 1) * st.session_state[f"{page_prefix}page_size"], len(filtered_files)
        )
        current_page_files = filtered_files[start_index:end_index]

        if not current_page_files:
           handle_error(page_prefix, "No charts on this page", error_type="info")
           return

        for chart_metadata in current_page_files:
            if st.session_state[f"{page_prefix}loading_all_charts"]:
                with st.spinner(f"Loading {chart_metadata[0]}..."):
                    display_metadata(chart_metadata)
                    await display_chart(page_prefix, chart_metadata, chart_height, use_async) # Add await
            else:
                break
    except Exception as e:
        handle_error(page_prefix, f"An unexpected error occurred while displaying charts: {e}", error_type="error")
    finally:
        update_session_state(page_prefix, "loading_all_charts", False)

def display_pagination_controls(page_prefix: str, filtered_files: List[Tuple[str, str, int, str]], page_size: int) -> None:
    """Displays pagination controls."""
    with st.container(): # Add a container
        st.markdown(
            """
            <style>
            .pagination-container {
                display: flex;
                justify-content: center;
                align-items: center;
                margin-top: 1em;
                margin-bottom: 1em;
            }
            .pagination-container > div {
                margin-right: 10px; /* Add spacing between elements */
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        col1, col2, col3 = st.columns([1, 3, 1]) # Use columns
        start_index = st.session_state[f"{page_prefix}page_number"] * page_size
        end_index = min(
            (st.session_state[f"{page_prefix}page_number"] + 1) * page_size, len(filtered_files)
        )
        total_pages = (len(filtered_files) + page_size - 1) // page_size

        with col1:
            prev_disabled = st.session_state[f"{page_prefix}page_number"] <= 0 or st.session_state[
                f"{page_prefix}loading"
            ]
            if st.button("Previous", disabled=prev_disabled, key=f"{page_prefix}prev_button"):
                update_session_state(page_prefix, "page_number", st.session_state[f"{page_prefix}page_number"] - 1)

        with col2:
            page_number_input = st.number_input(
                "Go to Page",
                min_value=1,
                max_value=total_pages,
                value=st.session_state[f"{page_prefix}page_number"] + 1,
                step=1,
                key=f"{page_prefix}page_input",
                on_change = lambda: update_session_state(page_prefix, "page_number", page_number_input - 1)
            )

            st.write(f"Page {st.session_state[f'{page_prefix}page_number'] + 1} / {total_pages}")

        with col3:
            next_disabled = end_index >= len(filtered_files) or st.session_state[
                f"{page_prefix}loading"
            ]
            if st.button("Next", disabled=next_disabled, key=f"{page_prefix}next_button"):
                update_session_state(page_prefix, "page_number", st.session_state[f"{page_prefix}page_number"] + 1)

def display_filters(page_prefix:str, file_types: List[str]) -> Tuple[str, List[str], str, int, int, bool]:
    """Displays the filter and setting controls in the sidebar"""
    with st.sidebar:
            search_query = st.text_input(
                "Search",
                value=st.session_state[f"{page_prefix}search_query"],
                placeholder="Enter chart name",
                max_chars=20,
                on_change=lambda: clear_error(page_prefix)
            )
            selected_types = st.multiselect(
                "Filter by Type",
                list(file_types),
                st.session_state[f"{page_prefix}selected_types"],
                on_change=lambda: clear_error(page_prefix)
            )
            sort_by = st.selectbox(
                "Sort by",
                ["Name", "Last Modified", "Size"],
                index=["Name", "Last Modified", "Size"].index(st.session_state[f"{page_prefix}sort_by"]),
                on_change=lambda: clear_error(page_prefix)
            )
            chart_height = st.slider(
                "Chart Height", 400, 1200, 600, on_change=lambda: clear_error(page_prefix)
            )
            page_size = st.selectbox(
                "Page Size",
                [5, 10, 20],
                index=[5, 10, 20].index(st.session_state[f"{page_prefix}page_size"]),
                label_visibility="visible",
                on_change=lambda: clear_error(page_prefix)
            )
            page_size = max(1, page_size)
            use_async = st.checkbox("Use Async Load", value=st.session_state[f"{page_prefix}use_async"], on_change=lambda: clear_error(page_prefix))
            return search_query, selected_types, sort_by, chart_height, page_size, use_async


async def main(chart_dir: Path) -> None:
    """Main function to set up and display the app."""

    page_prefix = get_page_prefix(chart_dir)
    init_session_state(page_prefix)

    # Inject custom CSS
    st.markdown(
        """
        <style>
        .st-emotion-cache-1v0mbdj {
          padding-top: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True
     )

    try:
        st.title(f"Interactive - {chart_dir.name}")

        # Load all files only if not already loaded.
        if not st.session_state[f"{page_prefix}all_files"]:
            with st.spinner("Loading charts..."):
                all_files_paths = get_all_json_files(chart_dir)
                if not all_files_paths:
                    return # Exit if no files
                all_files_metadata = [get_file_metadata(f) for f in all_files_paths]
                update_session_state(page_prefix, "all_files", tuple(all_files_metadata))  # Convert to tuple of tuples

        all_files = st.session_state[f"{page_prefix}all_files"]

        if not all_files:
            handle_error(page_prefix,"No chart files found in the selected directory.", error_type="warning")
            st.markdown(
                "**Instructions:**\n\n"
                 "1. Make sure that the subfolder contains JSON files ending with `.json` extension.\n"
            )
            return

        file_types = set(f[0].split('_')[0] for f in all_files)  # extract type from tuple

        # Error Message Display Area
        error_container = st.empty()

        # Sidebar for filters
        search_query, selected_types, sort_by, chart_height, page_size, use_async = display_filters(page_prefix, file_types)

        # Update session state based on sidebar interactions
        update_session_state(page_prefix, "search_query", search_query)
        update_session_state(page_prefix, "selected_types", selected_types)
        update_session_state(page_prefix, "sort_by", sort_by)
        update_session_state(page_prefix, "page_size", page_size)
        update_session_state(page_prefix, "use_async", use_async)


        # Filter and sort files
        with st.spinner("Filtering and sorting charts..."):
          filtered_files = filter_charts(all_files, search_query, selected_types)
          filtered_files = sort_files(filtered_files, sort_by)
          update_session_state(page_prefix, "filtered_files", tuple(filtered_files))
          filtered_files = st.session_state[f"{page_prefix}filtered_files"]


        if not filtered_files:
            handle_error(page_prefix, "No charts match the current filter criteria.", error_type="info")
            return

        # Pagination logic
        start_index = st.session_state[f"{page_prefix}page_number"] * page_size
        end_index = min((st.session_state[f"{page_prefix}page_number"] + 1) * page_size, len(filtered_files))
        current_page_files = filtered_files[start_index:end_index]


        if not current_page_files:
           handle_error(page_prefix, "No charts match the selected filters.", error_type="info")
           update_session_state(page_prefix, "loading_all_charts", False)
           st.selectbox("Select a chart", [], disabled=True, label_visibility="visible")
        else:
            # Display selected chart or all charts in current page
            chart_names = [f[0] for f in current_page_files] # Extract names from tuple
            selected_chart = st.selectbox(
                "Select a chart",
                ["Show All Charts"] + chart_names,
                index=0,
                key=f"{page_prefix}chart_selectbox",
                label_visibility="visible"
            )
            if selected_chart == "Show All Charts":
                if not st.session_state[f"{page_prefix}loading_all_charts"]:
                    update_session_state(page_prefix, "loading_all_charts", True)
                    await display_all_charts(page_prefix, filtered_files, chart_height, use_async)
                if st.button("Cancel Loading", disabled=not st.session_state[f"{page_prefix}loading_all_charts"], key=f"{page_prefix}cancel_loading"):
                    update_session_state(page_prefix, "loading_all_charts", False)
            elif selected_chart:
                chart_file = next((f for f in current_page_files if f[0] == selected_chart), None)
                if chart_file:
                    display_metadata(chart_file)
                    await display_chart(page_prefix, chart_file, chart_height, use_async)
            else:
                 handle_error(page_prefix, "Please select a chart.", error_type="info")
                 update_session_state(page_prefix, "loading_all_charts", False)


        # Pagination controls
        if filtered_files:  # Only display pagination controls if there are some files.
            display_pagination_controls(page_prefix, filtered_files, page_size)


    except Exception as e:
        handle_error(page_prefix, f"An unexpected error occurred: {e}", error_type="error")

if __name__ == "__main__":
    # Define the parent directory where chart directories are stored
    parent_directory = Path("assets")

    # Ensure the parent directory exists
    if not parent_directory.exists():
        st.error(
            "The 'assets' directory does not exist. Please create it and add subdirectories with charts.",
            icon="⚠️",
        )
        st.markdown(
            "**Instructions:**\n\n"
            "1. Create a directory named `assets` in the same folder as this script.\n"
            "2. Inside `assets`, create subfolders (e.g., `dir1`, `dir2`).\n"
            "3. Place your chart JSON files in these subfolders."
        )
    else:
        # Dynamically scan subdirectories
        chart_directories = [d for d in parent_directory.iterdir() if d.is_dir()]

        if not chart_directories:
            st.error(
                "No subdirectories found in the 'assets' directory. Please add subdirectories containing charts.",
                icon="⚠️",
            )
            st.markdown(
                "**Instructions:**\n\n"
                   "1. Inside the `assets` directory, create subfolders (e.g., `dir1`, `dir2`).\n"
                   "2. Place your chart JSON files in these subfolders."
            )
        else:
            # Sidebar for selecting a directory
            selected_dir = st.sidebar.selectbox(
                "Select Dashboard",
                chart_directories,
                format_func=lambda x: x.name,
                key="directory_selectbox",
                index = chart_directories.index(st.session_state.get("selected_dir", chart_directories[0])) if "selected_dir" in st.session_state else 0,
                on_change = lambda: update_session_state(get_page_prefix(selected_dir), "page_number", 0) # Reset page number when a new directory is selected

            )

            # Persist selected directory
            st.session_state["selected_dir"] = selected_dir

            # Call the main function with the selected directory
            asyncio.run(main(selected_dir))
