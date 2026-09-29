"""Regresión del hallazgo en vivo #8: el bootstrap con sandbox Docker real debe
activar el wheelhouse; si no, la instalación sin red falla y toda verificación
queda en 0/0 pruebas."""

from emh.bootstrap import Aplicacion


def test_bootstrap_activa_wheelhouse_con_sandbox_real(tmp_path):
    app = Aplicacion(data_dir=tmp_path, modo_simulado=True)
    try:
        assert app.entorno.usar_wheelhouse is True
    finally:
        app.cerrar()
