"""Fase 3 — Recuperación de la contraseña del Módulo 1 por correo electrónico.

Flujo: el usuario escribe su usuario o su correo → si la cuenta existe y tiene correo, se le envía un código de
6 dígitos → con el código elige una contraseña nueva, que se guarda como hash scrypt (src/autenticacion.py).

Seguridad:
- La respuesta es siempre la misma, exista o no la cuenta: no se puede averiguar qué usuarios hay.
- El código se genera con `secrets` y nunca se guarda: el servidor solo conserva su HMAC-SHA256 con una llave
  aleatoria que vive en la memoria del proceso (si la consola se reinicia, los códigos pendientes dejan de valer).
- Vence a los 15 minutos, admite 5 intentos y sirve una sola vez.
- Un envío por minuto y a lo sumo 5 por hora para cada usuario (evita llenar el buzón de alguien).
- Al cambiar la contraseña se avisa al correo de la cuenta.

Configuración (en .streamlit/secrets.toml, que NO se sube al repositorio):

    [usuarios.admin]
    ...
    correo = "persona@ejemplo.com"     # o: python -m src.autenticacion correo admin persona@ejemplo.com

    [correo]
    servidor = "smtp.gmail.com"
    puerto = 587                       # 587 = STARTTLS; 465 = SSL directo
    usuario = "cuenta.materna@gmail.com"
    clave = "contraseña de aplicación"  # en Gmail: verificación en dos pasos + «Contraseñas de aplicaciones»
    remitente = "MATERNA <cuenta.materna@gmail.com>"   # opcional; por defecto, el usuario
"""
import hashlib
import hmac
import secrets
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage

from src.autenticacion import LONGITUD_MINIMA, ROLES, cambiar_contrasena, leer_secretos

MINUTOS_VIGENCIA = 15
INTENTOS_CODIGO = 5
SEGUNDOS_ENTRE_ENVIOS = 60
ENVIOS_POR_HORA = 5
DIGITOS = 6

AVISO_ENVIO = (f"Si los datos corresponden a una cuenta con correo registrado, le enviamos un código de {DIGITOS} dígitos "
               f"(vence en {MINUTOS_VIGENCIA} minutos; revise también el spam).")
CODIGO_INVALIDO = "El código no es válido o ya venció. Pida uno nuevo."

_LLAVE = secrets.token_bytes(32)
_CANDADO = threading.Lock()
_CODIGOS = {}  # usuario -> {"huella", "expira", "intentos"}
_ENVIOS = {}   # usuario -> [momentos de envío de la última hora]


# ------------------------------------------------------------------ configuración
def config_correo(secretos=None):
    """Datos del servidor de correo, o None si falta algo (entonces la recuperación no está disponible)."""
    datos = dict((secretos if secretos is not None else leer_secretos()).get("correo", {}))
    if not all(datos.get(k) for k in ("servidor", "usuario", "clave")):
        return None
    datos["puerto"] = int(datos.get("puerto", 587))
    datos.setdefault("remitente", datos["usuario"])
    return datos


def enviar_correo(config, destinatario, asunto, cuerpo):
    """Envía un correo de texto por SMTP cifrado (SSL en el puerto 465; STARTTLS en los demás)."""
    mensaje = EmailMessage()
    mensaje["From"], mensaje["To"], mensaje["Subject"] = config["remitente"], destinatario, asunto
    mensaje.set_content(cuerpo)
    contexto = ssl.create_default_context()
    if config["puerto"] == 465:
        servidor = smtplib.SMTP_SSL(config["servidor"], 465, context=contexto, timeout=20)
    else:
        servidor = smtplib.SMTP(config["servidor"], config["puerto"], timeout=20)
        servidor.starttls(context=contexto)
    with servidor:
        servidor.login(config["usuario"], config["clave"])
        servidor.send_message(mensaje)


# ------------------------------------------------------------------ cuentas y códigos
def buscar_cuenta(identificador, usuarios):
    """(usuario, correo) si el identificador es un usuario o un correo registrado de una cuenta válida; si no, None."""
    texto = (identificador or "").strip().lower()
    if not texto:
        return None
    for usuario, datos in usuarios.items():
        correo = str(datos.get("correo", "")).strip().lower()
        if correo and datos.get("rol") in ROLES and texto in (usuario.lower(), correo):
            return usuario, correo
    return None


def _huella(usuario, codigo):
    return hmac.new(_LLAVE, f"{usuario}:{codigo}".encode(), hashlib.sha256).digest()


def solicitar(identificador, usuarios, config, enviar=None, ahora=None):
    """Genera y envía un código si corresponde. Devuelve True salvo si el correo no se pudo enviar.
    Que no exista la cuenta o que se pidan códigos demasiado seguido NO se distingue (también devuelve True)."""
    ahora = time.time() if ahora is None else ahora
    enviar = enviar or enviar_correo
    cuenta = buscar_cuenta(identificador, usuarios)
    if cuenta is None or config is None:
        return True
    usuario, correo = cuenta
    with _CANDADO:
        envios = [t for t in _ENVIOS.get(usuario, []) if ahora - t < 3600]
        if (envios and ahora - envios[-1] < SEGUNDOS_ENTRE_ENVIOS) or len(envios) >= ENVIOS_POR_HORA:
            _ENVIOS[usuario] = envios
            return True
        codigo = f"{secrets.randbelow(10 ** DIGITOS):0{DIGITOS}d}"
        _CODIGOS[usuario] = {"huella": _huella(usuario, codigo), "expira": ahora + MINUTOS_VIGENCIA * 60, "intentos": 0}
        _ENVIOS[usuario] = [*envios, ahora]
    try:
        enviar(config, correo, "MATERNA · código para restablecer su contraseña",
               f"Hola, {usuarios[usuario].get('nombre', usuario)}:\n\n"
               f"Su código para restablecer la contraseña del laboratorio MATERNA es:\n\n    {codigo}\n\n"
               f"Vence en {MINUTOS_VIGENCIA} minutos y sirve una sola vez. Si usted no lo pidió, ignore este correo: "
               "su contraseña no cambia.\n\nMATERNA · Universidad Popular del Cesar")
    except (OSError, smtplib.SMTPException):
        with _CANDADO:
            _CODIGOS.pop(usuario, None)
        return False
    return True


def restablecer(identificador, codigo, nueva, repetida, usuarios, config=None, enviar=None, ruta=None, ahora=None):
    """Cambia la contraseña si el código es correcto. Devuelve (True, mensaje) o (False, motivo)."""
    ahora = time.time() if ahora is None else ahora
    enviar = enviar or enviar_correo
    if len(nueva) < LONGITUD_MINIMA:
        return False, f"La contraseña nueva debe tener al menos {LONGITUD_MINIMA} caracteres."
    if nueva != repetida:
        return False, "Las dos contraseñas no coinciden."
    cuenta = buscar_cuenta(identificador, usuarios)
    codigo = (codigo or "").strip()
    with _CANDADO:
        pendiente = _CODIGOS.get(cuenta[0]) if cuenta else None
        if pendiente is None or ahora > pendiente["expira"]:
            if cuenta:
                _CODIGOS.pop(cuenta[0], None)
            return False, CODIGO_INVALIDO
        if not hmac.compare_digest(pendiente["huella"], _huella(cuenta[0], codigo)):
            pendiente["intentos"] += 1
            if pendiente["intentos"] >= INTENTOS_CODIGO:
                _CODIGOS.pop(cuenta[0], None)
                return False, "Demasiados intentos con un código incorrecto. Pida un código nuevo."
            return False, f"Código incorrecto. Le quedan {INTENTOS_CODIGO - pendiente['intentos']} intento(s)."
        _CODIGOS.pop(cuenta[0], None)  # un solo uso
    usuario, correo = cuenta
    cambiar_contrasena(usuario, nueva, ruta)
    if config is not None:
        try:  # el aviso es de cortesía: si falla, la contraseña ya cambió igual
            enviar(config, correo, "MATERNA · su contraseña cambió",
                   f"La contraseña de la cuenta «{usuario}» del laboratorio MATERNA se cambió el "
                   f"{time.strftime('%d/%m/%Y a las %H:%M', time.localtime(ahora))}.\n\n"
                   "Si no fue usted, avise de inmediato al administrador del sistema.")
        except (OSError, smtplib.SMTPException):
            pass
    return True, "Contraseña actualizada. Ya puede iniciar sesión con la nueva."


def _reiniciar():
    """Solo para las pruebas: olvida los códigos y envíos pendientes."""
    with _CANDADO:
        _CODIGOS.clear()
        _ENVIOS.clear()
