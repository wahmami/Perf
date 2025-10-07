import tomllib, pathlib, psycopg2
cfg = tomllib.loads(pathlib.Path(".streamlit/secrets.toml").read_text()).get("postgres", {})
print("host:", cfg.get("host"))
print("database:", cfg.get("database"))
try:
    conn = psycopg2.connect(
        host=cfg["host"],
        dbname=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
        port=cfg.get("port", 5432)
    )
    cur = conn.cursor()
    cur.execute("SELECT version();")
    print("Connected:", cur.fetchone())
    cur.close(); conn.close()
except Exception as e:
    print("Connection failed:", e)