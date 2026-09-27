from streamlit.testing.v1 import AppTest

def test_streamlit_app_loads_without_exceptions():
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    assert not at.exception, [str(x.value) for x in at.exception]
