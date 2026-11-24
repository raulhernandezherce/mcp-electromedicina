import json
import subprocess
import sys
import unittest
from pathlib import Path

from mcp_electromedicina.mantenimiento import fennigkoh_smith, planificar
from mcp_electromedicina.seguridad import evaluar

RAIZ = Path(__file__).resolve().parents[1]


class SeguridadTest(unittest.TestCase):
    def test_clase_I_CF_apta(self):
        r = evaluar("I", "CF", resistencia_tierra_ohm=0.12, fuga_equipo_uA=180, fuga_parte_aplicable_uA=8)
        self.assertEqual(r["veredicto"], "APTO")
        self.assertEqual(len(r["ensayos"]), 3)

    def test_fuga_CF_excesiva_no_apta(self):
        r = evaluar("I", "CF", resistencia_tierra_ohm=0.12, fuga_equipo_uA=180, fuga_parte_aplicable_uA=62)
        self.assertTrue(r["veredicto"].startswith("NO APTO"))

    def test_metodo_alternativo_es_mas_permisivo(self):
        self.assertTrue(evaluar("I", fuga_equipo_uA=800, resistencia_tierra_ohm=0.1)["veredicto"].startswith("NO APTO"))
        self.assertEqual(evaluar("I", metodo="alternativo", fuga_equipo_uA=800,
                                 resistencia_tierra_ohm=0.1)["veredicto"], "APTO")

    def test_clase_II_limite_100uA(self):
        self.assertTrue(evaluar("II", fuga_equipo_uA=150)["veredicto"].startswith("NO APTO"))

    def test_falta_tierra_en_clase_I(self):
        self.assertTrue(evaluar("I", fuga_equipo_uA=10)["veredicto"].startswith("INCOMPLETO"))

    def test_entrada_invalida(self):
        with self.assertRaises(ValueError):
            evaluar("III")


class MantenimientoTest(unittest.TestCase):
    def test_fennigkoh_smith(self):
        # desfibrilador: soporte vital (10), riesgo de muerte (5), mantenimiento medio (3)
        self.assertEqual(fennigkoh_smith(10, 5, 3)["EM"], 18)
        self.assertTrue(fennigkoh_smith(10, 5, 3)["incluir_en_preventivo"])
        self.assertFalse(fennigkoh_smith(2, 1, 1)["incluir_en_preventivo"])
        with self.assertRaises(ValueError):
            fennigkoh_smith(11, 1, 1)

    def test_planificar(self):
        inv = json.loads((RAIZ / "examples" / "inventario.json").read_text())
        r = planificar(inv, hoy="2026-11-24")
        self.assertEqual([f["id"] for f in r["vencidos"]], ["ECG-009"])          # vencido el 2026-11-02
        self.assertEqual([f["id"] for f in r["proximos"]], ["DEF-002", "MON-014", "BIN-031"])  # 7, 16 y 52 días
        self.assertEqual(r["vencidos"][0]["dias"], -22)

    def test_fin_de_mes(self):
        r = planificar([{"id": "x", "ultimo_preventivo": "2026-01-31", "periodicidad_meses": 1}],
                       hoy="2026-02-01")
        self.assertEqual(r["proximos"][0]["proximo_preventivo"], "2026-02-28")


class ProtocoloTest(unittest.TestCase):
    """Habla con el servidor por stdio, como lo haría Claude."""

    def conversar(self, *mensajes):
        entrada = "\n".join(json.dumps(m) for m in mensajes) + "\n"
        out = subprocess.run([sys.executable, "-m", "mcp_electromedicina"], cwd=RAIZ, input=entrada,
                             capture_output=True, text=True, timeout=10, check=True)
        return [json.loads(l) for l in out.stdout.splitlines()]

    def test_sesion_completa(self):
        r = self.conversar(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "puntuar_fennigkoh_smith", "arguments": {"funcion": 9, "riesgo": 4, "mantenimiento": 3}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "no_existe"}},
        )
        self.assertEqual([m["id"] for m in r], [1, 2, 3, 4])  # la notificación no se responde
        self.assertEqual(r[0]["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(len(r[1]["result"]["tools"]), 4)
        self.assertEqual(r[2]["result"]["structuredContent"]["EM"], 16)
        self.assertIn("error", r[3])

    def test_argumentos_erroneos_devuelven_isError(self):
        r = self.conversar({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                            "params": {"name": "evaluar_seguridad_electrica", "arguments": {"clase": "X"}}})
        self.assertTrue(r[0]["result"]["isError"])

    def test_json_roto_no_tumba_el_servidor(self):
        out = subprocess.run([sys.executable, "-m", "mcp_electromedicina"], cwd=RAIZ,
                             input='{roto\n{"jsonrpc":"2.0","id":9,"method":"ping"}\n',
                             capture_output=True, text=True, timeout=10)
        lineas = [json.loads(l) for l in out.stdout.splitlines()]
        self.assertEqual(lineas[0]["error"]["code"], -32700)
        self.assertEqual(lineas[1]["id"], 9)


if __name__ == "__main__":
    unittest.main()
