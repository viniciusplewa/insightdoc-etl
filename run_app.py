import os
import sys
import streamlit.web.cli as stcli

if __name__ == "__main__":
  script_path = os.path.join(os.path.dirname(__file__), "app.py")
  sys.argv = [
      "streamlit",
      "run",
      script_path,
      "--global.developmentMode=false",
  ]
  sys.exit(stcli.main())
