# Lead Recovery Dashboard v0.1.1 (File Upload)

This Streamlit application provides an interactive dashboard for analyzing and managing lead recovery data.

## Features (v0.1.1)

*   **Upload** `analysis.csv` directly via the sidebar.
*   Filters leads by creation date range and stall reason.
*   Displays Key Performance Indicators (KPIs):
    *   Total leads loaded (based on filters).
    *   Placeholders for "Contacted" and "Profile Completed".
    *   Bar chart showing the distribution of `stall_reason`.
*   Interactive table displaying lead details.
*   Clickable rows to expand and view full AI summary, key interaction, and suggestion.
*   Export button to download the currently filtered data as a CSV file.

## Prerequisites

*   Python >= 3.10
*   An `analysis.csv` file with the expected columns (see `dashboard/utils.py` for details).
*   An environment with the dashboard dependencies installed.

## Setup

1.  **Navigate to the project root directory** (the directory containing the `dashboard/` folder).
2.  **Install Dashboard Dependencies**: If you haven't already, install the required packages. It's recommended to do this within a virtual environment.
    ```bash
    pip install -r dashboard/requirements.txt
    ```

## Running the Dashboard

1.  **Run the Streamlit app** from the project root directory:
    ```bash
    streamlit run dashboard/streamlit_app.py
    ```
2.  The application will open in your default web browser.
3.  **Upload your `analysis.csv` file** using the file uploader widget in the sidebar.
4.  The dashboard will load and display the data once the file is uploaded.

## Project Structure

```
.                           # Project Root
├── dashboard/
│   ├── streamlit_app.py    # Main dashboard application script
│   ├── utils.py            # Helper functions (data loading, KPIs, etc.)
│   ├── requirements.txt    # Dashboard specific Python dependencies
│   └── README.md           # This file
└── ... (optional: output_run/, other package files)
```

## Future Development (TODOs)

*   **v0.2**: Implement functionality to post status updates (e.g., "Mark as Contacted") to a backend API.
*   **v0.3**: Add user authentication and role-based access control.
*   **v0.4**: Integrate click-to-call functionality (e.g., using Twilio). 