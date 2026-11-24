"""Evaluación de ensayos de seguridad eléctrica según los límites de IEC 62353.

Los valores son los de referencia habituales de IEC 62353:2014 (ensayos recurrentes y tras
reparación de equipos electromédicos). Verifica siempre con la edición vigente de la norma y
con las instrucciones del fabricante: este código ayuda a documentar, no sustituye al técnico.
"""

LIMITES = {
    "resistencia_tierra_ohm": 0.3,  # conductor de protección, incluido el cable de red
    "fuga_equipo_uA": {
        # método: {clase: límite}
        "directo": {"I": 500, "II": 100},
        "diferencial": {"I": 500, "II": 100},
        "alternativo": {"I": 1000, "II": 500},
    },
    "fuga_parte_aplicable_uA": {
        # solo partes aplicables tipo F (BF y CF)
        "directo": {"BF": 5000, "CF": 50},
        "alternativo": {"BF": 5000, "CF": 50},
    },
    # IEC 62353 no fija un límite de aislamiento; valor orientativo, solo genera un aviso
    "aislamiento_orientativo_Mohm": 2.0,
}

CLASES = ("I", "II")
TIPOS = ("B", "BF", "CF", "ninguna")
METODOS = ("directo", "diferencial", "alternativo")


def evaluar(clase, tipo_parte_aplicable="ninguna", metodo="directo", resistencia_tierra_ohm=None,
            fuga_equipo_uA=None, fuga_parte_aplicable_uA=None, aislamiento_Mohm=None):
    """Devuelve un informe con cada ensayo, su límite y el veredicto global."""
    clase, tipo, metodo = str(clase).upper(), str(tipo_parte_aplicable).upper(), str(metodo).lower()
    if tipo == "NINGUNA":
        tipo = "ninguna"
    if clase not in CLASES:
        raise ValueError(f"clase debe ser una de {CLASES}")
    if tipo not in TIPOS:
        raise ValueError(f"tipo_parte_aplicable debe ser uno de {TIPOS}")
    if metodo not in METODOS:
        raise ValueError(f"metodo debe ser uno de {METODOS}")

    ensayos, avisos = [], []

    def ensayo(nombre, valor, limite, unidad):
        ok = valor <= limite
        ensayos.append({"ensayo": nombre, "medido": valor, "limite": limite, "unidad": unidad,
                        "resultado": "APTO" if ok else "NO APTO"})

    if clase == "I":
        if resistencia_tierra_ohm is None:
            avisos.append("Clase I: falta la resistencia del conductor de protección (obligatoria).")
        else:
            ensayo("Resistencia del conductor de protección", resistencia_tierra_ohm,
                   LIMITES["resistencia_tierra_ohm"], "Ω")
    elif resistencia_tierra_ohm is not None:
        avisos.append("Clase II: no tiene conductor de protección; se ignora la resistencia de tierra.")

    if fuga_equipo_uA is not None:
        ensayo(f"Corriente de fuga del equipo ({metodo})", fuga_equipo_uA,
               LIMITES["fuga_equipo_uA"][metodo][clase], "µA")
    else:
        avisos.append("Falta la corriente de fuga del equipo.")

    if tipo in ("BF", "CF"):
        m = "alternativo" if metodo == "alternativo" else "directo"
        if fuga_parte_aplicable_uA is None:
            avisos.append(f"Parte aplicable {tipo}: falta la corriente de fuga de la parte aplicable.")
        else:
            ensayo(f"Corriente de fuga de la parte aplicable {tipo} ({m})", fuga_parte_aplicable_uA,
                   LIMITES["fuga_parte_aplicable_uA"][m][tipo], "µA")

    if aislamiento_Mohm is not None and aislamiento_Mohm < LIMITES["aislamiento_orientativo_Mohm"]:
        avisos.append(f"Aislamiento bajo ({aislamiento_Mohm} MΩ). IEC 62353 no fija límite: "
                      f"compara con mediciones anteriores y con el fabricante.")

    fallos = [e for e in ensayos if e["resultado"] == "NO APTO"]
    if fallos:
        veredicto = "NO APTO: retirar de uso, etiquetar y reparar antes de volver a servicio"
    elif any(a.startswith(("Falta", "Clase I: falta", "Parte aplicable")) for a in avisos):
        veredicto = "INCOMPLETO: faltan mediciones obligatorias"
    else:
        veredicto = "APTO"
    return {"equipo": {"clase": clase, "parte_aplicable": tipo, "metodo": metodo},
            "ensayos": ensayos, "avisos": avisos, "veredicto": veredicto,
            "referencia": "Límites de referencia IEC 62353:2014. Verifique con la edición vigente."}
