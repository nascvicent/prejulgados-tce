from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import sqlite3, os

app = FastAPI()
DB_PATH = os.environ.get("DB_PATH", "data/analise.db")

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS comentarios (
            usuario     TEXT NOT NULL,
            codigo      TEXT NOT NULL,
            texto       TEXT NOT NULL DEFAULT '',
            atualizado  DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (usuario, codigo)
        );
        CREATE TABLE IF NOT EXISTS vinculos (
            usuario     TEXT NOT NULL,
            grupo_id    TEXT NOT NULL,
            codigo      TEXT NOT NULL,
            PRIMARY KEY (usuario, grupo_id, codigo)
        );
    """)
    conn.commit()
    conn.close()

init_db()

class Comentario(BaseModel):
    texto: str

class VinculoPayload(BaseModel):
    links: dict

@app.get("/api/estado/{usuario}")
def get_estado(usuario: str):
    conn = get_db()
    rows_c = conn.execute(
        "SELECT codigo, texto FROM comentarios WHERE usuario=?", (usuario,)
    ).fetchall()
    comentarios = {r["codigo"]: r["texto"] for r in rows_c}

    rows_v = conn.execute(
        "SELECT grupo_id, codigo FROM vinculos WHERE usuario=? ORDER BY grupo_id",
        (usuario,)
    ).fetchall()
    vinculos = {}
    for r in rows_v:
        vinculos.setdefault(r["grupo_id"], []).append(r["codigo"])

    conn.close()
    return {"comentarios": comentarios, "vinculos": vinculos}

@app.post("/api/comentario/{usuario}/{codigo}")
def salvar_comentario(usuario: str, codigo: str, body: Comentario):
    conn = get_db()
    conn.execute("""
        INSERT INTO comentarios (usuario, codigo, texto) VALUES (?,?,?)
        ON CONFLICT(usuario, codigo)
        DO UPDATE SET texto=excluded.texto, atualizado=CURRENT_TIMESTAMP
    """, (usuario, codigo, body.texto))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.post("/api/vinculos/{usuario}")
def salvar_vinculos(usuario: str, body: VinculoPayload):
    conn = get_db()
    conn.execute("DELETE FROM vinculos WHERE usuario=?", (usuario,))
    for grupo_id, codigos in body.links.items():
        for codigo in codigos:
            conn.execute(
                "INSERT INTO vinculos (usuario, grupo_id, codigo) VALUES (?,?,?)",
                (usuario, grupo_id, codigo)
            )
    conn.commit()
    conn.close()
    return {"ok": True}

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")
