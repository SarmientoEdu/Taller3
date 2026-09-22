import os
import re
import sys
import glob
import subprocess
from datetime import datetime
from supabase import create_client, Client

# Variables de entorno desde GitHub Secrets
SUPABASE_URL = "https://ikusdplwwvcbxgvevkvw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlrdXNkcGx3d3ZjYnhndmV2a3Z3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg5ODgyMjYsImV4cCI6MjEwNDU2NDIyNn0.TEA3ZOmZxv7zedc2hDZUaDoB0oGDVMXM2yh1M6D4YBc"

COMMIT_SHA = os.environ.get("GITHUB_SHA", "unknown")

def parse_header():
    """Extrae la huella de nombres, cédulas y grupo desde el encabezado .java"""
    files = glob.glob("*.java")
    if not files:
        return None
    
    header_pattern = re.compile(
        r"/\*.*?"
        r"Grupo:\s*(?P<grupo>.*?)\n.*?"
        r"Integrante 1:\s*(?P<nombre1>.*?)\s*-\s*(?P<cedula1>.*?)\n.*?"
        r"Integrante 2:\s*(?P<nombre2>.*?)\s*-\s*(?P<cedula2>.*?)\n"
        r".*?\*/", re.DOTALL | re.IGNORECASE
    )

    for file_path in files:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            match = header_pattern.search(content)
            if match:
                return {
                    "grupo": match.group("grupo").strip(),
                    "nombre1": match.group("nombre1").strip(),
                    "cedula1": match.group("cedula1").strip(),
                    "nombre2": match.group("nombre2").strip(),
                    "cedula2": match.group("cedula2").strip()
                }
    return None

def grade_submission():
    """Ejecuta la compilación y pruebas del Taller N° 2"""
    puntos = 0
    feedback = []

    # 1. Verificación de Huella/Encabezado (10 pts)
    huella = parse_header()
    if huella and huella["cedula1"]:
        puntos += 10
        feedback.append("✓ Encabezado/Huella válido (+10 pts)")
    else:
        feedback.append("✗ Encabezado/Huella inválido o incompleto (0/10 pts)")
        # Valores por defecto si falla
        huella = {
            "grupo": "N/A",
            "nombre1": os.environ.get("GITHUB_ACTOR", "Desconocido"),
            "cedula1": f"GH-{os.environ.get('GITHUB_ACTOR')}",
            "nombre2": None,
            "cedula2": None
        }

    # 2. Compilación de FacturaTienda.java, Empleado.java y PruebaEmpleado.java (20 pts)
    compilation = subprocess.run(["javac", "FacturaTienda.java", "Empleado.java", "PruebaEmpleado.java"], capture_output=True, text=True)
    if compilation.returncode == 0:
        puntos += 20
        feedback.append("✓ Compilación exitosa (+20 pts)")
        
        # 3. Ejecución de FacturaTienda (35 pts)
        exec_factura = subprocess.run(["java", "FacturaTienda"], capture_output=True, text=True)
        if exec_factura.returncode == 0:
            puntos += 35
            feedback.append("✓ Ejecución de FacturaTienda (+35 pts)")
        else:
            feedback.append("✗ Error al ejecutar FacturaTienda")

        # 4. Ejecución de PruebaEmpleado (35 pts)
        exec_empleado = subprocess.run(["java", "PruebaEmpleado"], capture_output=True, text=True)
        if exec_empleado.returncode == 0:
            puntos += 35
            feedback.append("✓ Ejecución de PruebaEmpleado (+35 pts)")
        else:
            feedback.append("✗ Error al ejecutar PruebaEmpleado")
    else:
        feedback.append(f"✗ Error de compilación:\n{compilation.stderr}")

    return puntos, huella, "\n".join(feedback)

def save_to_supabase(huella, nota):
    """Realiza un Upsert en Supabase para mantener solo el último registro"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("WARN: Las credenciales de Supabase no están configuradas.")
        return

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    payload = {
        "estudiante_1": huella["nombre1"],
        "cedula_1": huella["cedula1"],
        "estudiante_2": huella.get("nombre2"),
        "cedula_2": huella.get("cedula2"),
        "grupo": huella.get("grupo"),
        "nota": nota,
        "commit_sha": COMMIT_SHA,
        "updated_at": datetime.utcnow().isoformat()
    }

    # Upsert con la restricción de cédulas
    response = supabase.table("calificaciones_taller").upsert(
        payload, on_conflict="cedula_1, cedula_2"
    ).execute()
    
    print("Resultado guardado en Supabase:", response)

if __name__ == "__main__":
    nota_final, datos_estudiantes, log = grade_submission()
    print("--- RESUMEN DE EVALUACIÓN ---")
    print(log)
    print(f"\nNota Final: {nota_final}/100")
    
    # Guardar en Supabase
    save_to_supabase(datos_estudiantes, nota_final)
    
    # Fallar el workflow si no alcanza nota mínima (opcional)
    if nota_final < 60:
        sys.exit(1)
