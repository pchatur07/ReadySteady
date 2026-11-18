"""Start the development server: python run.py  ->  http://127.0.0.1:5000"""
from app import create_app
from app.db import connect
from seed import seed

app = create_app()

if __name__ == "__main__":
    conn = connect(app.config["DATABASE"])
    if seed(conn):
        print("Loaded demo data.")
    conn.close()
    print("Logins: student@iiita.ac.in / student123 | staff@iiita.ac.in / staff1234 | admin@iiita.ac.in / admin1234")
    app.run(host="127.0.0.1", port=5000, debug=False)
