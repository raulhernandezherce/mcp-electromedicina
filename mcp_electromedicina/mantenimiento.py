"""Gestión del mantenimiento preventivo de un parque de equipos electromédicos.

Incluye el método de Fennigkoh y Smith (1989), muy usado en ingeniería clínica para decidir
qué equipos entran en el programa de mantenimiento preventivo:

    EM = función + riesgo físico + requisitos de mantenimiento + historial de incidencias

    función        2-10  (10 = soporte vital ... 2 = no relacionado con el paciente)
    riesgo físico  1-5   (5 = posible muerte del paciente ... 1 = sin riesgo apreciable)
    mantenimiento  1-5   (5 = extenso ... 1 = mínimo)
    historial      -2..+2

Con EM >= 12 el equipo se incluye en el programa de preventivo.
"""
from datetime import date, timedelta


def fennigkoh_smith(funcion, riesgo, mantenimiento, historial=0):
    rangos = {"funcion": (funcion, 2, 10), "riesgo": (riesgo, 1, 5),
              "mantenimiento": (mantenimiento, 1, 5), "historial": (historial, -2, 2)}
    for nombre, (v, lo, hi) in rangos.items():
        if not lo <= v <= hi:
            raise ValueError(f"{nombre} debe estar entre {lo} y {hi}")
    em = funcion + riesgo + mantenimiento + historial
    return {
        "EM": em,
        "incluir_en_preventivo": em >= 12,
        "nota": "El método decide la inclusión, no la frecuencia: usa la periodicidad del fabricante.",
    }


def _sumar_meses(d, meses):
    m = d.month - 1 + meses
    y, m = d.year + m // 12, m % 12 + 1
    dias = [31, 29 if y % 4 == 0 and (y % 100 or y % 400 == 0) else 28, 31, 30, 31, 30,
            31, 31, 30, 31, 30, 31][m - 1]
    return date(y, m, min(d.day, dias))


def planificar(inventario, hoy=None, horizonte_dias=60):
    """Ordena el inventario por urgencia: vencidos primero, después los próximos."""
    hoy = date.fromisoformat(hoy) if isinstance(hoy, str) else (hoy or date.today())
    limite = hoy + timedelta(days=horizonte_dias)
    vencidos, proximos = [], []
    for eq in inventario:
        ultima = date.fromisoformat(eq["ultimo_preventivo"])
        prox = _sumar_meses(ultima, int(eq["periodicidad_meses"]))
        fila = {"id": eq.get("id"), "equipo": eq.get("equipo"), "ubicacion": eq.get("ubicacion"),
                "proximo_preventivo": prox.isoformat(), "dias": (prox - hoy).days}
        if prox < hoy:
            vencidos.append(fila)
        elif prox <= limite:
            proximos.append(fila)
    vencidos.sort(key=lambda f: f["dias"])
    proximos.sort(key=lambda f: f["dias"])
    return {"fecha": hoy.isoformat(), "vencidos": vencidos, "proximos": proximos,
            "resumen": f"{len(vencidos)} vencidos y {len(proximos)} en los próximos {horizonte_dias} días "
                       f"de {len(inventario)} equipos."}
