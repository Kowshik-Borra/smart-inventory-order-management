import os
from streamlit.testing.v1 import AppTest
import app

APP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))

def test_all_pages_render():
    for page_name in app.PAGE_ROUTES.keys():
        at = AppTest.from_file(APP_PATH, default_timeout=25)
        at.session_state["authenticated"] = True
        at.session_state["admin_id"] = 1
        at.session_state["username"] = "kowshik"
        at.session_state["full_name"] = "System Administrator"
        at.session_state["role"] = "Super Admin"
        at.session_state["current_page"] = page_name
        at.run()
        assert not at.exception, f"Exception on page {page_name}: {at.exception}"

if __name__ == "__main__":
    test_all_pages_render()
    print("ALL 12 PAGES TESTED AND PASSED SUCCESSFULLY!")
