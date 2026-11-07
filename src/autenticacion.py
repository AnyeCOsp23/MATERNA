"""Fase 3 — Usuarios, contraseñas y permisos del Módulo 1 (Laboratorio de ML, Streamlit).

El Módulo 1 sirve para REVISAR el sistema: lo usan el docente, los evaluadores y el médico auditor
de la IPS. El personal de salud que USA el sistema con las gestantes (médico, enfermería, auxiliar o
partera) entra al Módulo 2 (app Flutter, web y móvil), con su propio inicio de sesión por PIN.

Las contraseñas nunca se guardan: solo su hash scrypt con una sal aleatoria por usuario.
Los usuarios viven en .streamlit/secrets.toml (fuera del repositorio) bajo [usuarios.<nombre>]:

    [usuarios.profe]
    nombre = "Evaluador académico"
    rol = "evaluador"
    hash = "scrypt$16384$8$1$<sal>$<hash>"

La variable de entorno MATERNA_USUARIOS puede apuntar a otro archivo TOML con la misma
estructura (lo usan las pruebas).

Crear un usuario (pide la contraseña sin mostrarla y agrega el bloque al archivo):
    python -m src.autenticacion crear-usuario profe --rol evaluador --nombre "Tony Jiménez"
"""
import argparse
import base64
import getpass
import hashlib
import hmac
import os
import secrets
import tomllib
from pathlib import Path

from src.config import RAIZ

RUTA_SECRETS = RAIZ / ".streamlit" / "secrets.toml"
VARIABLE_USUARIOS = "MATERNA_USUARIOS"
LONGITUD_MINIMA = 8
INTENTOS_MAXIMOS = 5
SCRYPT = {"n": 2**14, "r": 8, "p": 1}

ROLES = {
    "administrador": "Administrador",
    "medico_auditor": "Médico auditor",
    "evaluador": "Evaluador académico",
}
# Qué puede hacer cada rol en el laboratorio:
# - administrador: todo, incluido reentrenar;
# - médico auditor (de la IPS): audita el laboratorio e ingiere y guarda archivos reales de la IPS;
# - evaluador académico: audita todo en modo lectura (la ingesta, solo con el ejemplo ficticio).
PERMISOS = {
    "administrador": {"laboratorio", "variables_3280", "triaje", "ingesta_archivos", "entrenar"},
    "medico_auditor": {"laboratorio", "variables_3280", "triaje", "ingesta_archivos"},
    "evaluador": {"laboratorio", "variables_3280", "triaje"},
}


def _b64(datos):
    return base64.b64encode(datos).decode("ascii")


def generar_hash(contrasena):
    if len(contrasena) < LONGITUD_MINIMA:
        raise ValueError(f"La contraseña debe tener al menos {LONGITUD_MINIMA} caracteres.")
    sal = secrets.token_bytes(16)
    clave = hashlib.scrypt(contrasena.encode("utf-8"), salt=sal, **SCRYPT)
    return f"scrypt${SCRYPT['n']}${SCRYPT['r']}${SCRYPT['p']}${_b64(sal)}${_b64(clave)}"


def verificar_hash(contrasena, almacenado):
    try:
        esquema, n, r, p, sal, clave = almacenado.split("$")
        if esquema != "scrypt":
            return False
        calculada = hashlib.scrypt(contrasena.encode("utf-8"), salt=base64.b64decode(sal),
                                   n=int(n), r=int(r), p=int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calculada, base64.b64decode(clave))


def cargar_usuarios(secretos=None):
    """Usuarios desde MATERNA_USUARIOS (si existe) o desde los secretos de Streamlit."""
    ruta = os.environ.get(VARIABLE_USUARIOS)
    if ruta:
        with open(ruta, "rb") as f:
            return tomllib.load(f).get("usuarios", {})
    if secretos is None:
        return {}
    try:
        return {k: dict(v) for k, v in secretos.get("usuarios", {}).items()}
    except Exception:  # st.secrets sin secrets.toml lanza su propio error
        return {}


def autenticar(usuario, contrasena, usuarios):
    """Devuelve {'usuario', 'nombre', 'rol'} si las credenciales son válidas; si no, None."""
    datos = usuarios.get(usuario.strip().lower())
    if not datos or datos.get("rol") not in ROLES:
        # Igual se calcula un hash para que el tiempo de respuesta no revele si el usuario existe
        verificar_hash(contrasena, "scrypt$16384$8$1$AAAAAAAAAAAAAAAAAAAAAA==$AAAA")
        return None
    if not verificar_hash(contrasena, datos.get("hash", "")):
        return None
    return {"usuario": usuario.strip().lower(), "nombre": datos.get("nombre", usuario), "rol": datos["rol"]}


def puede(usuario, permiso):
    return usuario is not None and permiso in PERMISOS.get(usuario["rol"], set())


def bloque_toml(usuario, rol, nombre, contrasena):
    if rol not in ROLES:
        raise ValueError(f"Rol desconocido: {rol}. Use uno de: {', '.join(ROLES)}")
    return f'\n[usuarios.{usuario.strip().lower()}]\nnombre = "{nombre}"\nrol = "{rol}"\nhash = "{generar_hash(contrasena)}"\n'


def main():
    parser = argparse.ArgumentParser(description="Usuarios de la consola web de MATERNA")
    sub = parser.add_subparsers(dest="accion", required=True)
    crear = sub.add_parser("crear-usuario", help="crea un usuario y lo agrega a .streamlit/secrets.toml")
    crear.add_argument("usuario")
    crear.add_argument("--rol", required=True, choices=list(ROLES))
    crear.add_argument("--nombre", required=True)
    crear.add_argument("--archivo", default=str(RUTA_SECRETS))
    args = parser.parse_args()

    contrasena = getpass.getpass("Contraseña: ")
    if contrasena != getpass.getpass("Repita la contraseña: "):
        raise SystemExit("Las contraseñas no coinciden.")
    bloque = bloque_toml(args.usuario, args.rol, args.nombre, contrasena)
    ruta = Path(args.archivo)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(bloque)
    print(f"Usuario '{args.usuario}' ({ROLES[args.rol]}) agregado a {ruta}. Reinicie la consola para usarlo.")


if __name__ == "__main__":
    main()
