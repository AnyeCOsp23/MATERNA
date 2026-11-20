"""Fase 3: «¿Olvidó su contraseña?» del Módulo 1 (src/recuperacion.py). Ningún correo sale de verdad: el envío se simula."""
import re
import tomllib

import pytest
from streamlit.testing.v1 import AppTest

from conftest import RAIZ
from src import recuperacion
from src.autenticacion import actualizar_campo, autenticar, bloque_toml, cargar_usuarios, correo_valido

APP = str(RAIZ / "app_demo.py")
CORREO = {"servidor": "smtp.ejemplo.com", "puerto": 587, "usuario": "materna@ejemplo.com", "clave": "x"}
CLAVE = "clave-admin-123"


class Buzon:
    """Reemplaza al servidor de correo: guarda lo que se habría enviado."""
    def __init__(self, falla=False):
        self.enviados, self.falla = [], falla

    def __call__(self, config, destinatario, asunto, cuerpo):
        if self.falla:
            raise OSError("sin conexión")
        self.enviados.append((destinatario, asunto, cuerpo))

    def codigo(self):
        return re.search(r"\b(\d{6})\b", self.enviados[-1][2]).group(1)


@pytest.fixture
def archivo(tmp_path, monkeypatch):
    ruta = tmp_path / "usuarios.toml"
    ruta.write_text(bloque_toml("admin", "administrador", "Administrador", CLAVE, "Admin@Ejemplo.com")
                    + bloque_toml("medico", "medico_auditor", "Médico", "clave-medico-123")  # sin correo
                    + '\n[correo]\nservidor = "smtp.ejemplo.com"\nusuario = "materna@ejemplo.com"\nclave = "x"\n',
                    encoding="utf-8")
    monkeypatch.setenv("MATERNA_USUARIOS", str(ruta))
    recuperacion._reiniciar()
    yield ruta
    recuperacion._reiniciar()


def usuarios():
    return cargar_usuarios()


# ------------------------------------------------------------------ módulo
def test_flujo_completo_cambia_la_contrasena(archivo):
    buzon = Buzon()
    assert recuperacion.solicitar("admin", usuarios(), CORREO, enviar=buzon)
    destinatario, asunto, cuerpo = buzon.enviados[0]
    assert destinatario == "admin@ejemplo.com" and "código" in asunto
    codigo = buzon.codigo()
    ok, _ = recuperacion.restablecer("admin", codigo, "nueva-clave-456", "nueva-clave-456", usuarios(), CORREO, enviar=buzon)
    assert ok
    assert autenticar("admin", "nueva-clave-456", usuarios()) and not autenticar("admin", CLAVE, usuarios())
    assert "cambió" in buzon.enviados[-1][1]  # aviso de que la contraseña cambió
    # el archivo sigue completo: el otro usuario y el correo no se tocaron, y la contraseña no se escribió
    datos = tomllib.loads(archivo.read_text(encoding="utf-8"))
    assert set(datos["usuarios"]) == {"admin", "medico"} and datos["correo"]["servidor"] == "smtp.ejemplo.com"
    assert "nueva-clave-456" not in archivo.read_text(encoding="utf-8")
    # el código sirve una sola vez
    ok, _ = recuperacion.restablecer("admin", codigo, "otra-clave-789", "otra-clave-789", usuarios(), CORREO, enviar=buzon)
    assert not ok


def test_tambien_por_correo_y_sin_distinguir_mayusculas(archivo):
    buzon = Buzon()
    recuperacion.solicitar("  ADMIN@ejemplo.com ", usuarios(), CORREO, enviar=buzon)
    assert len(buzon.enviados) == 1


def test_no_revela_si_la_cuenta_existe(archivo):
    buzon = Buzon()
    # usuario inexistente y usuario sin correo: misma respuesta y ningún correo
    assert recuperacion.solicitar("nadie", usuarios(), CORREO, enviar=buzon) is True
    assert recuperacion.solicitar("medico", usuarios(), CORREO, enviar=buzon) is True
    assert not buzon.enviados
    assert recuperacion.restablecer("nadie", "123456", "nueva-clave-456", "nueva-clave-456", usuarios())[1] == recuperacion.CODIGO_INVALIDO


def test_codigo_incorrecto_vencido_e_intentos(archivo):
    buzon = Buzon()
    recuperacion.solicitar("admin", usuarios(), CORREO, enviar=buzon, ahora=1000)
    bueno = buzon.codigo()
    malo = f"{(int(bueno) + 1) % 10 ** 6:06d}"
    for _ in range(recuperacion.INTENTOS_CODIGO - 1):
        ok, mensaje = recuperacion.restablecer("admin", malo, "nueva-clave-456", "nueva-clave-456", usuarios(), ahora=1001)
        assert not ok and "incorrecto" in mensaje
    ok, mensaje = recuperacion.restablecer("admin", malo, "nueva-clave-456", "nueva-clave-456", usuarios(), ahora=1001)
    assert not ok and "Demasiados intentos" in mensaje
    # agotados los intentos, ni el código bueno sirve
    assert not recuperacion.restablecer("admin", bueno, "nueva-clave-456", "nueva-clave-456", usuarios(), ahora=1002)[0]
    # vencido: pasado el plazo no sirve
    recuperacion.solicitar("admin", usuarios(), CORREO, enviar=buzon, ahora=2000)
    vence = 2000 + recuperacion.MINUTOS_VIGENCIA * 60 + 1
    assert recuperacion.restablecer("admin", buzon.codigo(), "nueva-clave-456", "nueva-clave-456", usuarios(),
                                    ahora=vence)[1] == recuperacion.CODIGO_INVALIDO
    assert autenticar("admin", CLAVE, usuarios())  # la contraseña no cambió


def test_contrasena_nueva_valida(archivo):
    buzon = Buzon()
    recuperacion.solicitar("admin", usuarios(), CORREO, enviar=buzon)
    assert "al menos" in recuperacion.restablecer("admin", buzon.codigo(), "corta", "corta", usuarios())[1]
    assert "no coinciden" in recuperacion.restablecer("admin", buzon.codigo(), "nueva-clave-456", "otra-cosa-456", usuarios())[1]
    # los errores de la contraseña no gastan el código
    assert recuperacion.restablecer("admin", buzon.codigo(), "nueva-clave-456", "nueva-clave-456", usuarios())[0]


def test_limite_de_envios(archivo):
    buzon = Buzon()
    recuperacion.solicitar("admin", usuarios(), CORREO, enviar=buzon, ahora=0)
    recuperacion.solicitar("admin", usuarios(), CORREO, enviar=buzon, ahora=10)  # menos de un minuto: no se envía
    assert len(buzon.enviados) == 1
    for minuto in range(1, 10):
        recuperacion.solicitar("admin", usuarios(), CORREO, enviar=buzon, ahora=minuto * 61)
    assert len(buzon.enviados) == recuperacion.ENVIOS_POR_HORA
    recuperacion.solicitar("admin", usuarios(), CORREO, enviar=buzon, ahora=3700)  # pasó la hora
    assert len(buzon.enviados) == recuperacion.ENVIOS_POR_HORA + 1


def test_falla_del_correo_no_deja_codigo_valido(archivo):
    assert recuperacion.solicitar("admin", usuarios(), CORREO, enviar=Buzon(falla=True)) is False
    assert recuperacion.restablecer("admin", "000000", "nueva-clave-456", "nueva-clave-456", usuarios())[1] == recuperacion.CODIGO_INVALIDO


def test_configuracion_del_correo():
    assert recuperacion.config_correo({}) is None
    assert recuperacion.config_correo({"correo": {"servidor": "s", "usuario": "u"}}) is None  # falta la clave
    config = recuperacion.config_correo({"correo": {"servidor": "s", "usuario": "u@x.co", "clave": "c"}})
    assert config["puerto"] == 587 and config["remitente"] == "u@x.co"


def test_actualizar_campo_conserva_el_archivo(tmp_path):
    ruta = tmp_path / "secrets.toml"
    ruta.write_bytes(b'MATERNA_SAL = "abc"\r\n\r\n[usuarios.admin]\r\nnombre = "A"\r\nrol = "administrador"\r\nhash = "h1"\r\n'
                     b'\r\n[usuarios.medico]\r\nnombre = "M"\r\nrol = "medico_auditor"\r\nhash = "h2"\r\n')
    actualizar_campo("admin", "hash", "nuevo", ruta)
    actualizar_campo("medico", "correo", "m@x.co", ruta)
    datos = tomllib.loads(ruta.read_text(encoding="utf-8"))
    assert datos["MATERNA_SAL"] == "abc" and datos["usuarios"]["admin"]["hash"] == "nuevo"
    assert datos["usuarios"]["medico"] == {"nombre": "M", "rol": "medico_auditor", "hash": "h2", "correo": "m@x.co"}
    assert b"\r\n" in ruta.read_bytes() and b"\n\n" not in ruta.read_bytes().replace(b"\r\n", b"")  # mismos saltos de línea
    with pytest.raises(KeyError):
        actualizar_campo("nadie", "hash", "x", ruta)
    with pytest.raises(ValueError):
        actualizar_campo("admin", "hash", 'x"\n[usuarios.intruso]', ruta)
    assert correo_valido("a@b.co") and not correo_valido("sin-arroba") and not correo_valido('a"@b.co')


# ------------------------------------------------------------------ en la app
def app_abierta():
    at = AppTest.from_file(APP, default_timeout=180)
    at.session_state["bienvenida_mostrada"] = True
    return at.run()


def boton(at, texto):
    return next(b for b in at.button if b.label == texto)


def test_login_sin_el_mensaje_viejo_y_con_el_enlace(archivo):
    at = app_abierta()
    assert not any("Para revisar el sistema" in c.value for c in at.caption)
    assert boton(at, "¿Olvidó su contraseña?")


def test_recuperar_desde_la_app(archivo, monkeypatch):
    buzon = Buzon()
    monkeypatch.setattr(recuperacion, "enviar_correo", buzon)
    at = app_abierta()
    boton(at, "¿Olvidó su contraseña?").click().run()
    assert any("Recuperar la contraseña" in m.value for m in at.markdown)
    at.text_input[0].input("admin")
    boton(at, "Enviar el código").click().run()
    assert not at.exception and len(buzon.enviados) == 1
    assert any(recuperacion.AVISO_ENVIO in i.value for i in at.info)
    codigo, nueva, repetida = at.text_input
    codigo.input("000000" if buzon.codigo() != "000000" else "111111")
    nueva.input("nueva-clave-456")
    repetida.input("nueva-clave-456")
    boton(at, "Cambiar la contraseña").click().run()
    assert any("Código incorrecto" in e.value for e in at.error)
    at.text_input[0].input(buzon.codigo())
    boton(at, "Cambiar la contraseña").click().run()
    assert not at.exception
    assert any("Contraseña actualizada" in s.value for s in at.success)
    # de vuelta en el login, la contraseña nueva entra al laboratorio
    at.text_input[0].input("admin")
    at.text_input[1].input("nueva-clave-456")
    at.button[0].click().run()
    assert not at.exception and at.session_state["usuario"]["usuario"] == "admin"


def test_sin_correo_configurado_lo_dice(tmp_path, monkeypatch):
    ruta = tmp_path / "usuarios.toml"
    ruta.write_text(bloque_toml("admin", "administrador", "Administrador", CLAVE, "admin@ejemplo.com"), encoding="utf-8")
    monkeypatch.setenv("MATERNA_USUARIOS", str(ruta))
    at = app_abierta()
    boton(at, "¿Olvidó su contraseña?").click().run()
    assert any("no está configurada" in i.value for i in at.info)
    boton(at, "Volver al inicio de sesión").click().run()
    assert [t.label for t in at.text_input] == ["Usuario", "Contraseña"]
