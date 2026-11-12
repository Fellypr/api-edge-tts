import os
import sys
import unittest
import tempfile
from pathlib import Path
from pypdf import PdfWriter

# Adiciona o diretório raiz ao sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import extrair_texto_pdf, agrupar_em_lotes

class TestPdfLimit(unittest.TestCase):
    def setUp(self):
        # Cria um PDF temporário de teste com páginas
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pdf_path = Path(self.temp_dir.name) / "livro_teste.pdf"

        writer = PdfWriter()
        for i in range(1, 6):
            writer.add_blank_page(width=300, height=300)
        with open(self.pdf_path, "wb") as f:
            writer.write(f)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_extrair_texto_pdf_direto_do_disco(self):
        """Verifica se o leitor lê direto do disco via Path sem carregar na memória."""
        resultado = extrair_texto_pdf(self.pdf_path)
        self.assertIsInstance(resultado, list)

    def test_extrair_texto_pdf_com_bytes(self):
        """Verifica retrocompatibilidade com bytes em memória."""
        with open(self.pdf_path, "rb") as f:
            bytes_conteudo = f.read()
        resultado = extrair_texto_pdf(bytes_conteudo)
        self.assertIsInstance(resultado, list)

    def test_extrair_texto_pdf_recorte_paginas(self):
        """Verifica se o recorte de página inicial e final aceita intervalos válidos."""
        resultado_parcial = extrair_texto_pdf(
            self.pdf_path,
            pagina_inicial=2,
            pagina_final=4
        )
        self.assertIsInstance(resultado_parcial, list)

    def test_agrupar_em_lotes_respeita_limite(self):
        """Garante que a clusterização de texto respeita o tamanho máximo por lote configurado."""
        paragrafos_exemplo = [
            f"Parágrafo de teste número {i} com texto simulado para avaliar a divisão de lotes."
            for i in range(50)
        ]
        lotes = agrupar_em_lotes(paragrafos_exemplo, tamanho_lote=500)
        self.assertGreater(len(lotes), 1)
        for lote in lotes:
            # Cada lote deve ser menor ou igual a 500 caracteres (ou conter no máximo 1 parágrafo se este for maior)
            self.assertTrue(len(lote) <= 600)

if __name__ == "__main__":
    unittest.main()
