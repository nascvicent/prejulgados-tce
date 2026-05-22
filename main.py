from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os, psycopg2, psycopg2.extras
from contextlib import contextmanager

app = FastAPI()
DATABASE_URL = os.environ.get("DATABASE_URL")

@contextmanager
def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comentarios (
                usuario     TEXT NOT NULL,
                codigo      TEXT NOT NULL,
                texto       TEXT NOT NULL DEFAULT '',
                atualizado  TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (usuario, codigo)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vinculos (
                usuario     TEXT NOT NULL,
                grupo_id    TEXT NOT NULL,
                codigo      TEXT NOT NULL,
                PRIMARY KEY (usuario, grupo_id, codigo)
            )
        """)

init_db()

class Comentario(BaseModel):
    texto: str

class VinculoPayload(BaseModel):
    links: dict

@app.get("/api/estado/{usuario}")
def get_estado(usuario: str):
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT codigo, texto FROM comentarios WHERE usuario=%s", (usuario,))
        comentarios = {r["codigo"]: r["texto"] for r in cur.fetchall()}
        cur.execute("SELECT grupo_id, codigo FROM vinculos WHERE usuario=%s ORDER BY grupo_id", (usuario,))
        vinculos = {}
        for r in cur.fetchall():
            vinculos.setdefault(r["grupo_id"], []).append(r["codigo"])
    return {"comentarios": comentarios, "vinculos": vinculos}

@app.post("/api/comentario/{usuario}/{codigo}")
def salvar_comentario(usuario: str, codigo: str, body: Comentario):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO comentarios (usuario, codigo, texto)
            VALUES (%s, %s, %s)
            ON CONFLICT (usuario, codigo)
            DO UPDATE SET texto=EXCLUDED.texto, atualizado=NOW()
        """, (usuario, codigo, body.texto))
    return {"ok": True}

@app.post("/api/vinculos/{usuario}")
def salvar_vinculos(usuario: str, body: VinculoPayload):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM vinculos WHERE usuario=%s", (usuario,))
        for grupo_id, codigos in body.links.items():
            for codigo in codigos:
                cur.execute(
                    "INSERT INTO vinculos (usuario, grupo_id, codigo) VALUES (%s, %s, %s)",
                    (usuario, grupo_id, codigo)
                )
    return {"ok": True}

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")
