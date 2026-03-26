#!/usr/bin/env python3.14
"""Genera documentos sintéticos de peticiones clínicas con barcodes.

Uso:
    python3.14 docs/generate_sample_docs.py
    Salida: docs/sample_docs/peticion_*.png (6 documentos)
"""

from __future__ import annotations

import io
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import barcode
from barcode.writer import ImageWriter

OUTPUT_DIR = Path(__file__).parent / "sample_docs"

# Datos ficticios
NOMBRES = [
    ("García López", "María", "1985-04-12", "F"),
    ("Martínez Ruiz", "Pedro", "1972-11-03", "M"),
    ("Fernández Díaz", "Ana", "1990-07-22", "F"),
    ("Sánchez Torres", "Carlos", "1968-01-15", "M"),
    ("Rodríguez Vega", "Laura", "1995-09-30", "F"),
    ("Pérez Moreno", "Juan", "1980-06-18", "M"),
]

MEDICOS = [
    "Dra. Isabel Navarro — Col. 28/12345",
    "Dr. Antonio Molina — Col. 08/67890",
    "Dra. Carmen Ortega — Col. 46/11223",
    "Dr. Francisco Ramos — Col. 28/44556",
]

CENTROS = [
    "Hospital Universitario La Paz — Madrid",
    "Hospital Clínic — Barcelona",
    "Hospital La Fe — Valencia",
    "Hospital Virgen del Rocío — Sevilla",
]

PRUEBAS_GRUPOS = [
    ("HEMATOLOGÍA", [
        "Hemograma completo",
        "Velocidad de sedimentación (VSG)",
        "Recuento de reticulocitos",
        "Frotis de sangre periférica",
    ]),
    ("BIOQUÍMICA", [
        "Glucosa basal",
        "Hemoglobina glicosilada (HbA1c)",
        "Perfil lipídico (CT, HDL, LDL, TG)",
        "Función hepática (GOT, GPT, GGT, FA)",
        "Función renal (Creatinina, Urea, Ác. úrico)",
        "Iones (Na+, K+, Cl-)",
        "Proteína C reactiva (PCR)",
        "Ferritina",
    ]),
    ("HORMONAS", [
        "TSH",
        "T4 libre",
        "T3 libre",
        "Cortisol basal",
        "Vitamina D (25-OH)",
        "Vitamina B12",
        "Ácido fólico",
    ]),
    ("ORINA", [
        "Sedimento urinario",
        "Microalbuminuria",
        "Proteinuria 24h",
    ]),
    ("SEROLOGÍA", [
        "VIH 1/2 (Ag/Ac)",
        "Hepatitis B (HBsAg, Anti-HBs, Anti-HBc)",
        "Hepatitis C (Anti-VHC)",
        "RPR / VDRL",
    ]),
    ("COAGULACIÓN", [
        "Tiempo de protrombina (TP/INR)",
        "Tiempo de tromboplastina (TTPA)",
        "Fibrinógeno",
        "Dímero D",
    ]),
]


def _generate_barcode_image(code: str, width_px: int = 400) -> Image.Image:
    """Genera una imagen de barcode Code128."""
    writer = ImageWriter()
    writer.set_options({
        "module_width": 0.4,
        "module_height": 18,
        "font_size": 14,
        "text_distance": 5,
        "quiet_zone": 2,
    })
    bc = barcode.get("code128", code, writer=writer)
    buf = io.BytesIO()
    bc.write(buf)
    buf.seek(0)
    img = Image.open(buf).convert("RGB")
    # Redimensionar manteniendo proporción
    ratio = width_px / img.width
    new_h = int(img.height * ratio)
    return img.resize((width_px, new_h), Image.Resampling.LANCZOS)


def _draw_text(draw: ImageDraw.Draw, x: int, y: int, text: str,
               font: ImageFont.FreeTypeFont | None = None,
               fill: str = "#000000") -> int:
    """Dibuja texto y devuelve la altura usada."""
    draw.text((x, y), text, fill=fill, font=font)
    bbox = draw.textbbox((x, y), text, font=font)
    return bbox[3] - bbox[1]


def generate_document(
    idx: int,
    apellidos: str,
    nombre: str,
    fecha_nac: str,
    sexo: str,
) -> None:
    """Genera un documento de petición clínica como imagen PNG."""
    # Configuración de página (A4 a 150 DPI aprox)
    W, H = 1240, 1754
    img = Image.new("RGB", (W, H), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    # Intentar cargar fuentes del sistema
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        font_subtitle = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        font_normal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
        font_section = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except OSError:
        font_title = font_subtitle = font_normal = font_small = font_section = None

    # Generar códigos
    nhc = f"{random.randint(100000, 999999)}"
    peticion = f"P{random.randint(2026000001, 2026999999)}"
    episodio = f"E{random.randint(100000, 999999)}"
    fecha_pet = f"2026-03-{random.randint(20, 26):02d}"
    medico = random.choice(MEDICOS)
    centro = random.choice(CENTROS)

    y = 40
    margin = 60

    # ── Cabecera ──
    # Logo simulado (cruz médica)
    draw.rectangle([margin, y, margin + 50, y + 50], fill="#2196F3")
    draw.text((margin + 12, y + 8), "+", fill="#FFFFFF", font=font_title)

    _draw_text(draw, margin + 65, y + 5, "LABORATORIO DE ANÁLISIS CLÍNICOS", font=font_title, fill="#1565C0")
    y += 35
    _draw_text(draw, margin + 65, y + 5, centro, font=font_normal, fill="#555555")
    y += 50

    # Línea separadora
    draw.line([(margin, y), (W - margin, y)], fill="#1565C0", width=3)
    y += 15

    # ── Título ──
    _draw_text(draw, margin, y, "VOLANTE DE PETICIÓN ANALÍTICA", font=font_subtitle, fill="#1565C0")
    y += 40

    # ── Datos del paciente ──
    draw.rectangle([margin, y, W - margin, y + 160], outline="#CCCCCC", width=1)
    draw.rectangle([margin, y, W - margin, y + 30], fill="#E3F2FD")
    _draw_text(draw, margin + 10, y + 5, "DATOS DEL PACIENTE", font=font_section, fill="#1565C0")
    y += 38

    campos = [
        (f"Apellidos: {apellidos}", f"Nombre: {nombre}"),
        (f"Fecha nacimiento: {fecha_nac}", f"Sexo: {sexo}"),
        (f"NHC: {nhc}", f"Nº Episodio: {episodio}"),
    ]
    for left, right in campos:
        _draw_text(draw, margin + 15, y, left, font=font_normal)
        _draw_text(draw, W // 2 + 30, y, right, font=font_normal)
        y += 28

    y += 25

    # ── Datos de la petición ──
    draw.rectangle([margin, y, W - margin, y + 100], outline="#CCCCCC", width=1)
    draw.rectangle([margin, y, W - margin, y + 30], fill="#E8F5E9")
    _draw_text(draw, margin + 10, y + 5, "DATOS DE LA PETICIÓN", font=font_section, fill="#2E7D32")
    y += 38

    _draw_text(draw, margin + 15, y, f"Nº Petición: {peticion}", font=font_normal)
    _draw_text(draw, W // 2 + 30, y, f"Fecha: {fecha_pet}", font=font_normal)
    y += 28
    _draw_text(draw, margin + 15, y, f"Médico solicitante: {medico}", font=font_normal)
    y += 45

    # ── Pruebas solicitadas ──
    draw.rectangle([margin, y, W - margin, y + 30], fill="#FFF3E0")
    _draw_text(draw, margin + 10, y + 5, "PRUEBAS SOLICITADAS", font=font_section, fill="#E65100")
    y += 40

    # Seleccionar 2-4 grupos aleatorios
    n_groups = random.randint(2, 4)
    selected_groups = random.sample(PRUEBAS_GRUPOS, n_groups)

    col_width = (W - 2 * margin) // 2
    start_y = y

    for gi, (group_name, pruebas) in enumerate(selected_groups):
        col = gi % 2
        if gi == 2:
            start_y = y + 10
        cx = margin + col * col_width

        # Nombre del grupo
        _draw_text(draw, cx + 10, start_y if col == 0 else start_y,
                   f"■ {group_name}", font=font_section, fill="#333333")
        local_y = (start_y if col == 0 else start_y) + 25

        # Seleccionar algunas pruebas del grupo
        n_pruebas = random.randint(2, min(5, len(pruebas)))
        selected = random.sample(pruebas, n_pruebas)

        for prueba in selected:
            # Checkbox
            check_x = cx + 20
            draw.rectangle([check_x, local_y + 2, check_x + 14, local_y + 16],
                           outline="#666666", width=1)
            # Marcar algunos como checked
            if random.random() > 0.15:
                draw.line([(check_x + 2, local_y + 9), (check_x + 6, local_y + 14)],
                          fill="#2196F3", width=2)
                draw.line([(check_x + 6, local_y + 14), (check_x + 12, local_y + 4)],
                          fill="#2196F3", width=2)

            _draw_text(draw, check_x + 22, local_y, prueba, font=font_normal)
            local_y += 24

        if col == 0:
            y = max(y, local_y)
        else:
            y = max(y, local_y)
            start_y = y + 10

    if len(selected_groups) % 2 == 1:
        y = max(y, start_y + 25 * 5)

    y += 30

    # ── Observaciones ──
    if y < H - 350:
        draw.rectangle([margin, y, W - margin, y + 80], outline="#CCCCCC", width=1)
        draw.rectangle([margin, y, W - margin, y + 28], fill="#F3E5F5")
        _draw_text(draw, margin + 10, y + 4, "OBSERVACIONES CLÍNICAS", font=font_section, fill="#6A1B9A")
        y += 35
        observaciones = [
            "Paciente en seguimiento por diabetes tipo 2. Control trimestral.",
            "Revisión anual. Antecedentes familiares de hipercolesterolemia.",
            "Control post-tratamiento con levotiroxina. Ajuste de dosis.",
            "Estudio inicial por astenia y pérdida de peso no explicada.",
            "Control preoperatorio. Cirugía programada para abril 2026.",
            "Paciente anticoagulado con sintrom. Control mensual de INR.",
        ]
        _draw_text(draw, margin + 15, y, random.choice(observaciones), font=font_normal, fill="#555555")
        y += 50

    # ── Barcode inferior (NHC) ──
    y = H - 200
    draw.line([(margin, y - 10), (W - margin, y - 10)], fill="#CCCCCC", width=1)

    bc_nhc = _generate_barcode_image(nhc, width_px=250)
    img.paste(bc_nhc, (margin, y))

    bc_ep = _generate_barcode_image(episodio, width_px=250)
    img.paste(bc_ep, (W // 2 - 125, y))

    # Segundo barcode de petición abajo a la derecha
    bc_pet2 = _generate_barcode_image(peticion, width_px=250)
    img.paste(bc_pet2, (W - 250 - margin, y))

    # ── Pie ──
    y = H - 50
    _draw_text(draw, margin, y, f"Documento generado automáticamente — {centro}",
               font=font_small, fill="#AAAAAA")
    _draw_text(draw, W - margin - 200, y, f"Página 1 de 1",
               font=font_small, fill="#AAAAAA")

    # Guardar
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / f"peticion_{idx:02d}.png"
    img.save(filepath, "PNG", dpi=(150, 150))
    print(f"  {filepath.name} — {apellidos}, {nombre} — {peticion}")


def main() -> None:
    print("Generando documentos de ejemplo...")
    random.seed(42)  # Reproducible

    for i, (apellidos, nombre, fecha, sexo) in enumerate(NOMBRES, 1):
        generate_document(i, apellidos, nombre, fecha, sexo)

    print(f"\n{len(NOMBRES)} documentos generados en {OUTPUT_DIR}/")
    print("Importa estos ficheros en DocScan Studio para hacer capturas de pantalla.")


if __name__ == "__main__":
    main()
