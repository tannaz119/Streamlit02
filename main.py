
import streamlit.web.bootstrap

if __name__ == "__main__":
    streamlit.web.bootstrap.run("app.py", "", args=["--server.port=8501", "--server.address=0.0.0.0"], flag_options={})
