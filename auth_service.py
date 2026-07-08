# Trigger buggy webhook check
import sqlite3
import subprocess

def unsafe_login(username: str, system_cmd: str) -> None:
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # Vulnerability: SQL Injection
    query = f"SELECT * FROM accounts WHERE name = '{username}'"
    cursor.execute(query)
    
    # Vulnerability: Command Injection (RCE)
    subprocess.Popen(f"ping {system_cmd}", shell=True)
