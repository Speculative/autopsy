"""Generate test fixture for TreeView drag and drop testing."""

from autopsy import report, generate_html

def process_users():
    """Process multiple users with consistent data structure."""
    users = [
        {
            "user": {
                "name": "Alice",
                "age": 25,
                "city": "New York"
            },
            "status": "active"
        },
        {
            "user": {
                "name": "Bob",
                "age": 30,
                "city": "San Francisco"
            },
            "status": "active"
        },
        {
            "user": {
                "name": "Charlie",
                "age": 35,
                "city": "Chicago"
            },
            "status": "inactive"
        }
    ]

    for user_data in users:
        # Log each user - the user_data object itself will appear in the table
        # This creates columns with nested objects that can be expanded in table cells
        report.log("Processing user", user_data["user"]["name"], user_data)

if __name__ == "__main__":
    report.init(clear=True)
    process_users()
    generate_html(output_path="tests/e2e/fixtures/treeview_drag.html")
    print("Generated tests/e2e/fixtures/treeview_drag.html")
