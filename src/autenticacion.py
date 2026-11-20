"""Fase 3 — Usuarios, contraseñas y permisos del Módulo 1 (Laboratorio de ML, Streamlit).

El Módulo 1 sirve para REVISAR el sistema: lo usan el equipo (administrador) y el médico auditor
de la IPS; en la sustentación se opera con el administrador. El personal de salud que USA el sistema con las gestantes (médico, enfermería, auxiliar o
partera) entra al Módulo 2 (app Flutter, web y móvil), con su propio inicio de sesión por PIN.

Las contraseñas nunca se guardan: solo su hash scrypt con una sal aleatoria por usuario.
Los usuarios viven en .streamlit/secrets.toml (fuera del repositorio) bajo [usuarios.<nombre>]:

    [usuarios.medico]
    nombre = "Médico auditor"
    rol = "medico_auditor"
    hash = "scrypt$16384$8$1$<sal>$<hash>"

La variable de entorno MATERNA_USUARIOS puede apuntar a otro archivo TOML con la misma
estructura (lo usan las pruebas).

Crear un usuario (pide la contraseña sin mostrarla y agrega el bloque al archivo):
    python -m src.autenticacion crear-usuario medico --rol medico_auditor --nombre "Médico auditor" --correo medico@ejemplo.com

Asignar el correo de recuperación a un usuario que ya existe (lo usa «¿Olvidó su contraseña?», ver src/recuperacion.py):
    python -m src.autenticacion correo admin persona@ejemplo.com
"""
import argparse
import base64
import getpass
import hashlib
import hmac
import os
import re
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
}
# Qué puede hacer cada rol en el laboratorio:
# - administrador: todo, incluido reentrenar;
# - médico auditor (de la IPS): audita el laboratorio e ingiere y guarda archivos reales de la IPS; no reentrena.
# Un usuario con cualquier otro rol (p. ej. el antiguo "evaluador") no puede iniciar sesión.
PERMISOS = {
    "administrador": {"laboratorio", "variables_3280", "triaje", "ingesta_archivos", "entrenar"},
    "medico_auditor": {"laboratorio", "variables_3280", "triaje", "ingesta_archivos"},
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


def ruta_usuarios():
    """Archivo donde viven los usuarios: MATERNA_USUARIOS (pruebas) o .streamlit/secrets.toml."""
    return Path(os.environ.get(VARIABLE_USUARIOS) or RUTA_SECRETS)


def leer_secretos():
    """El archivo de usuarios completo (usuarios y configuración del correo); vacío si no existe."""
    ruta = ruta_usuarios()
    if not ruta.exists():
        return {}
    with open(ruta, "rb") as f:
        return tomllib.load(f)


def cargar_usuarios(secretos=None):
    """Usuarios desde MATERNA_USUARIOS o .streamlit/secrets.toml, leídos del archivo en cada llamada: así una
    contraseña recién restablecida vale de inmediato (st.secrets se recarga solo, pero con retraso).
    Si no hay archivo (p. ej. secretos configurados en un servidor), se usan los secretos de Streamlit."""
    if os.environ.get(VARIABLE_USUARIOS) or RUTA_SECRETS.exists():
        return {k: dict(v) for k, v in leer_secretos().get("usuarios", {}).items()}
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


def correo_valido(correo):
    return bool(re.fullmatch(r'[^@\s"\\]+@[^@\s"\\]+\.[^@\s"\\]+', correo or ""))


def bloque_toml(usuario, rol, nombre, contrasena, correo=None):
    if rol not in ROLES:
        raise ValueError(f"Rol desconocido: {rol}. Use uno de: {', '.join(ROLES)}")
    if correo is not None and not correo_valido(correo):
        raise ValueError(f"Correo no válido: {correo}")
    linea_correo = f'correo = "{correo.strip().lower()}"\n' if correo else ""
    return (f'\n[usuarios.{usuario.strip().lower()}]\nnombre = "{nombre}"\nrol = "{rol}"\n{linea_correo}'
            f'hash = "{generar_hash(contrasena)}"\n')


def actualizar_campo(usuario, campo, valor, ruta=None):
    """Cambia (o agrega) `campo = "valor"` en el bloque [usuarios.<usuario>] del archivo, sin tocar nada más.
    Escribe en un archivo temporal y lo reemplaza de una vez: un corte a mitad no deja el archivo a medias."""
    if '"' in valor or "\\" in valor or "\n" in valor:
        raise ValueError("El valor no puede llevar comillas, barras invertidas ni saltos de línea.")
    ruta = Path(ruta or ruta_usuarios())
    lineas = ruta.read_bytes().decode("utf-8").splitlines(keepends=True)  # conserva \r\n si el archivo los usa
    cabecera = re.compile(rf"^\s*\[usuarios\.{re.escape(usuario)}\]\s*$")
    inicio = next((i for i, linea in enumerate(lineas) if cabecera.match(linea)), None)
    if inicio is None:
        raise KeyError(f"No existe el usuario {usuario}")
    fin = next((i for i in range(inicio + 1, len(lineas)) if lineas[i].lstrip().startswith("[")), len(lineas))
    salto = "\r\n" if lineas[inicio].endswith("\r\n") else "\n"
    nueva = f'{campo} = "{valor}"{salto}'
    clave = re.compile(rf"^\s*{re.escape(campo)}\s*=")
    existente = next((i for i in range(inicio + 1, fin) if clave.match(lineas[i])), None)
    if existente is None:
        lineas.insert(inicio + 1, nueva)
    else:
        lineas[existente] = nueva
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text("".join(lineas), encoding="utf-8", newline="")
    os.replace(temporal, ruta)
    if tomllib.loads(ruta.read_text(encoding="utf-8"))["usuarios"][usuario].get(campo) != valor:
        raise RuntimeError("El archivo de usuarios no quedó como se esperaba.")


def cambiar_contrasena(usuario, contrasena, ruta=None):
    """Guarda el hash scrypt de la nueva contraseña (la contraseña nunca se escribe)."""
    actualizar_campo(usuario, "hash", generar_hash(contrasena), ruta)


def main():
    parser = argparse.ArgumentParser(description="Usuarios de la consola web de MATERNA")
    sub = parser.add_subparsers(dest="accion", required=True)
    crear = sub.add_parser("crear-usuario", help="crea un usuario y lo agrega a .streamlit/secrets.toml")
    crear.add_argument("usuario")
    crear.add_argument("--rol", required=True, choices=list(ROLES))
    crear.add_argument("--nombre", required=True)
    crear.add_argument("--correo", help="correo para recuperar la contraseña (opcional)")
    crear.add_argument("--archivo", default=str(RUTA_SECRETS))
    correo = sub.add_parser("correo", help="asigna o cambia el correo de recuperación de un usuario existente")
    correo.add_argument("usuario")
    correo.add_argument("correo")
    correo.add_argument("--archivo", default=str(RUTA_SECRETS))
    args = parser.parse_args()

    if args.accion == "correo":
        if not correo_valido(args.correo):
            raise SystemExit(f"Correo no válido: {args.correo}")
        try:
            actualizar_campo(args.usuario.strip().lower(), "correo", args.correo.strip().lower(), args.archivo)
        except KeyError as error:
            raise SystemExit(str(error))
        print(f"Correo de recuperación de '{args.usuario}' guardado en {args.archivo}.")
        return

    contrasena = getpass.getpass("Contraseña: ")
    if contrasena != getpass.getpass("Repita la contraseña: "):
        raise SystemExit("Las contraseñas no coinciden.")
    bloque = bloque_toml(args.usuario, args.rol, args.nombre, contrasena, args.correo)
    ruta = Path(args.archivo)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(bloque)
    print(f"Usuario '{args.usuario}' ({ROLES[args.rol]}) agregado a {ruta}. Reinicie la consola para usarlo.")


if __name__ == "__main__":
    main()
