"""Servidor MCP (Model Context Protocol) para electromedicina, sin dependencias.

Implementa el transporte stdio de MCP: mensajes JSON-RPC 2.0, uno por línea.
Se conecta a Claude Desktop, Claude Code o cualquier cliente MCP.

    python3 -m mcp_electromedicina
"""
import json
import sys
import traceback

from . import __version__
from .mantenimiento import fennigkoh_smith, planificar
from .seguridad import CLASES, LIMITES, METODOS, TIPOS, evaluar

VERSIONES = ("2025-06-18", "2025-03-26", "2024-11-05")

HERRAMIENTAS = [
    {
        "name": "evaluar_seguridad_electrica",
        "description": (
            "Evalúa las mediciones de un ensayo de seguridad eléctrica de un equipo electromédico "
            "frente a los límites de IEC 62353 (ensayo recurrente o tras reparación). Devuelve cada "
            "ensayo con su límite, avisos por mediciones que faltan y el veredicto APTO / NO APTO."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "clase": {"type": "string", "enum": list(CLASES), "description": "Clase de protección"},
                "tipo_parte_aplicable": {"type": "string", "enum": list(TIPOS), "default": "ninguna"},
                "metodo": {"type": "string", "enum": list(METODOS), "default": "directo",
                           "description": "Método de medida de la corriente de fuga"},
                "resistencia_tierra_ohm": {"type": "number"},
                "fuga_equipo_uA": {"type": "number"},
                "fuga_parte_aplicable_uA": {"type": "number"},
                "aislamiento_Mohm": {"type": "number"},
            },
            "required": ["clase"],
        },
    },
    {
        "name": "limites_iec_62353",
        "description": "Devuelve la tabla de límites de referencia de IEC 62353 que usa el servidor.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "puntuar_fennigkoh_smith",
        "description": (
            "Calcula la puntuación EM de Fennigkoh y Smith para decidir si un equipo entra en el "
            "programa de mantenimiento preventivo (EM >= 12). función 2-10, riesgo 1-5, "
            "mantenimiento 1-5, historial de incidencias -2..+2."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "funcion": {"type": "integer", "minimum": 2, "maximum": 10},
                "riesgo": {"type": "integer", "minimum": 1, "maximum": 5},
                "mantenimiento": {"type": "integer", "minimum": 1, "maximum": 5},
                "historial": {"type": "integer", "minimum": -2, "maximum": 2, "default": 0},
            },
            "required": ["funcion", "riesgo", "mantenimiento"],
        },
    },
    {
        "name": "planificar_preventivos",
        "description": (
            "Recibe un inventario de equipos con su último preventivo y su periodicidad y devuelve "
            "los vencidos y los próximos, ordenados por urgencia."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "inventario": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "equipo": {"type": "string"},
                            "ubicacion": {"type": "string"},
                            "ultimo_preventivo": {"type": "string", "format": "date"},
                            "periodicidad_meses": {"type": "integer", "minimum": 1},
                        },
                        "required": ["ultimo_preventivo", "periodicidad_meses"],
                    },
                },
                "hoy": {"type": "string", "format": "date", "description": "Por defecto, la fecha actual"},
                "horizonte_dias": {"type": "integer", "default": 60},
            },
            "required": ["inventario"],
        },
    },
]

FUNCIONES = {
    "evaluar_seguridad_electrica": lambda a: evaluar(**a),
    "limites_iec_62353": lambda a: LIMITES,
    "puntuar_fennigkoh_smith": lambda a: fennigkoh_smith(**a),
    "planificar_preventivos": lambda a: planificar(**a),
}


def manejar(msg):
    """Procesa un mensaje JSON-RPC y devuelve la respuesta (o None si es una notificación)."""
    metodo, id_, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if id_ is None:  # notificación (p. ej. notifications/initialized): no se responde
        return None

    def ok(result):
        return {"jsonrpc": "2.0", "id": id_, "result": result}

    if metodo == "initialize":
        pedida = params.get("protocolVersion")
        return ok({
            "protocolVersion": pedida if pedida in VERSIONES else VERSIONES[0],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "mcp-electromedicina", "version": __version__},
            "instructions": "Herramientas de ingeniería clínica: seguridad eléctrica IEC 62353 y "
                            "mantenimiento preventivo. Los resultados apoyan al técnico, no lo sustituyen.",
        })
    if metodo == "ping":
        return ok({})
    if metodo == "tools/list":
        return ok({"tools": HERRAMIENTAS})
    if metodo == "tools/call":
        nombre = params.get("name")
        if nombre not in FUNCIONES:
            return {"jsonrpc": "2.0", "id": id_,
                    "error": {"code": -32602, "message": f"Herramienta desconocida: {nombre}"}}
        try:
            datos = FUNCIONES[nombre](params.get("arguments") or {})
            return ok({"content": [{"type": "text", "text": json.dumps(datos, ensure_ascii=False, indent=2)}],
                       "structuredContent": datos, "isError": False})
        except (TypeError, ValueError, KeyError) as e:
            return ok({"content": [{"type": "text", "text": f"Error en los argumentos: {e}"}], "isError": True})
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": -32601, "message": f"Método no soportado: {metodo}"}}


def main():
    for linea in sys.stdin:
        linea = linea.strip()
        if not linea:
            continue
        try:
            respuesta = manejar(json.loads(linea))
        except json.JSONDecodeError:
            respuesta = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON no válido"}}
        except Exception:  # nunca tumbar el servidor; el detalle va a stderr (no contamina stdout)
            traceback.print_exc(file=sys.stderr)
            respuesta = None
        if respuesta is not None:
            sys.stdout.write(json.dumps(respuesta, ensure_ascii=False) + "\n")
            sys.stdout.flush()
